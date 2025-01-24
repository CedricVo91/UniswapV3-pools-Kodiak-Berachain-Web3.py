from web3 import Web3
from eth_account import Account
import json
import math
from typing import Tuple, Dict, Any, List

class KodiakV3PoolVerification:
    """
    A class to verify and debug Uniswap V3 pool state, focusing on:
    1. Active tick tracking
    2. Liquidity availability across tick ranges
    3. Position initialization status
    """
    def __init__(self, pool_address: str, nft_manager_address: str, rpc_url: str):
        # Initialize web3 connection
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.pool_address = Web3.to_checksum_address(pool_address)
        self.nft_manager_address = Web3.to_checksum_address(nft_manager_address)
        
        # Load contract ABIs
        with open("pool_abi.json", "r") as f:
            pool_abi = json.load(f)
        with open("nft_manager_abi.json", "r") as f:
            nft_manager_abi = json.load(f)
            
        # Create contract instances
        self.pool = self.w3.eth.contract(address=self.pool_address, abi=pool_abi)
        self.nft_manager = self.w3.eth.contract(address=self.nft_manager_address, abi=nft_manager_abi)

    def check_active_tick(self) -> Dict[str, Any]:
        """
        Check the current active tick and related pool state.
        This shows us where in the price range we're currently operating.
        """
        try:
            # Get slot0 data which contains current tick and price
            slot0 = self.pool.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            current_tick = slot0[1]
            
            # Convert sqrtPriceX96 to actual price
            price = (sqrt_price_x96 / (2**96)) ** 2
            
            # Get current liquidity
            current_liquidity = self.pool.functions.liquidity().call()
            
            return {
                'current_tick': current_tick,
                'sqrt_price_x96': sqrt_price_x96,
                'price': price,
                'current_liquidity': current_liquidity,
                'pool_unlocked': slot0[6]
            }
        except Exception as e:
            raise RuntimeError(f"Failed to check active tick: {str(e)}")

    def verify_liquidity_range(self, tick_lower: int, tick_upper: int) -> Dict[str, Any]:
        """
        Verify liquidity availability in a specific tick range.
        This helps us understand if there's tradeable liquidity at our target price points.
        """
        try:
            # Check if ticks are initialized
            tick_lower_info = self.pool.functions.ticks(tick_lower).call()
            tick_upper_info = self.pool.functions.ticks(tick_upper).call()
            
            # Get liquidity and time data for the range
            cumulative_data = self.pool.functions.snapshotCumulativesInside(
                tick_lower,
                tick_upper
            ).call()
            
            return {
                'tick_lower_initialized': tick_lower_info[0] > 0,  # liquidityGross > 0
                'tick_upper_initialized': tick_upper_info[0] > 0,
                'tick_lower_liquidity': tick_lower_info[0],
                'tick_upper_liquidity': tick_upper_info[0],
                'seconds_inside': cumulative_data[2]  # Time spent in this range
            }
        except Exception as e:
            raise RuntimeError(f"Failed to verify liquidity range: {str(e)}")

    def check_position_initialization(self, position_id: int, owner_address: str) -> Dict[str, Any]:
        """
        Check if a specific liquidity position is properly initialized.
        This verifies that our liquidity is correctly placed and accessible.
        """
        try:
            # Get position details from NFT manager
            position = self.nft_manager.functions.positions(position_id).call()
            
            # Verify owner matches
            is_owner = position[4].lower() == owner_address.lower()
            
            # Get liquidity details
            tick_lower = position[5]
            tick_upper = position[6]
            liquidity = position[7]
            
            # Check if position's ticks are initialized in the pool
            lower_tick_initialized = self.pool.functions.ticks(tick_lower).call()[0] > 0
            upper_tick_initialized = self.pool.functions.ticks(tick_upper).call()[0] > 0
            
            return {
                'is_owner': is_owner,
                'tick_lower': tick_lower,
                'tick_upper': tick_upper,
                'liquidity': liquidity,
                'lower_tick_initialized': lower_tick_initialized,
                'upper_tick_initialized': upper_tick_initialized,
                'fee_growth_inside': position[8:10],  # Fee growth inside the tick range
                'tokens_owed': position[10:12]  # Tokens owed to position
            }
        except Exception as e:
            raise RuntimeError(f"Failed to check position initialization: {str(e)}")

    def verify_swap_path(self, amount_in: int, zero_for_one: bool) -> Dict[str, Any]:
        """
        Verify if a swap path exists for the given parameters.
        This helps diagnose why swaps might be failing.
        """
        try:
            # Get current state
            current_state = self.check_active_tick()
            current_tick = current_state['current_tick']
            
            # Calculate next tick range
            tick_spacing = self.pool.functions.tickSpacing().call()
            next_tick = (current_tick // tick_spacing) * tick_spacing
            if zero_for_one:
                next_tick = next_tick - tick_spacing
            else:
                next_tick = next_tick + tick_spacing
                
            # Check liquidity in the next tick range
            liquidity_info = self.verify_liquidity_range(
                min(current_tick, next_tick),
                max(current_tick, next_tick)
            )
            
            # Try to quote the swap
            try:
                quote = self.pool.functions.quote(
                    amount_in,
                    current_state['sqrt_price_x96'],
                    zero_for_one
                ).call()
                can_swap = True
            except Exception:
                can_swap = False
                quote = None
            
            return {
                'current_tick': current_tick,
                'next_tick': next_tick,
                'tick_spacing': tick_spacing,
                'liquidity_available': liquidity_info['tick_lower_liquidity'] > 0,
                'can_swap': can_swap,
                'quoted_amount_out': quote[0] if quote else None,
                'sqrt_price_limit': quote[1] if quote else None
            }
        except Exception as e:
            raise RuntimeError(f"Failed to verify swap path: {str(e)}")

    def run_full_diagnosis(self, position_id: int, owner_address: str) -> Dict[str, Any]:
        """
        Run a complete diagnostic check of the pool and position state.
        This combines all verifications to give a complete picture of the setup.
        """
        diagnosis = {}
        
        # 1. Check current pool state
        diagnosis['pool_state'] = self.check_active_tick()
        
        # 2. Check position details
        diagnosis['position_state'] = self.check_position_initialization(
            position_id, 
            owner_address
        )
        
        # 3. Verify liquidity in relevant ranges
        current_tick = diagnosis['pool_state']['current_tick']
        position_lower = diagnosis['position_state']['tick_lower']
        position_upper = diagnosis['position_state']['tick_upper']
        
        # Check liquidity around current tick
        diagnosis['current_range_liquidity'] = self.verify_liquidity_range(
            current_tick - 10,
            current_tick + 10
        )
        
        # Check position range liquidity
        diagnosis['position_range_liquidity'] = self.verify_liquidity_range(
            position_lower,
            position_upper
        )
        
        # 4. Verify swap paths
        diagnosis['swap_path_info'] = {
            'zero_to_one': self.verify_swap_path(1000000, True),  # Test with 1 token
            'one_to_zero': self.verify_swap_path(1000000, False)
        }
        
        return diagnosis

def main():
    # Example usage
    rpc_url = "https://bartio.rpc.berachain.com"
    pool_address = "0x031634e7190162ade35C80516D958F3dF6a5C513"
    nft_manager_address = "0xc0568c6e9d5404124c8aa9efd955f3f14c8e64a6"
    position_id = 34883  # Your NFT position ID
    owner_address = "0x50199d4274E898d3E09B335fD233ADC55544F223"
    
    verifier = KodiakV3PoolVerification(pool_address, nft_manager_address, rpc_url)
    
    try:
        # Run complete diagnosis
        diagnosis = verifier.run_full_diagnosis(position_id, owner_address)
        
        # Print results in a readable format
        print("\n=== Pool State ===")
        print(f"Current Tick: {diagnosis['pool_state']['current_tick']}")
        print(f"Current Price: {diagnosis['pool_state']['price']}")
        print(f"Total Liquidity: {diagnosis['pool_state']['current_liquidity']}")
        
        print("\n=== Position State ===")
        print(f"Tick Range: {diagnosis['position_state']['tick_lower']} to {diagnosis['position_state']['tick_upper']}")
        print(f"Position Liquidity: {diagnosis['position_state']['liquidity']}")
        
        print("\n=== Liquidity Availability ===")
        print(f"Current Range Liquidity Available: {diagnosis['current_range_liquidity']['tick_lower_liquidity']}")
        print(f"Position Range Properly Initialized: {diagnosis['position_state']['lower_tick_initialized']} and {diagnosis['position_state']['upper_tick_initialized']}")
        
        print("\n=== Swap Path Verification ===")
        print(f"Can Swap Token0 to Token1: {diagnosis['swap_path_info']['zero_to_one']['can_swap']}")
        print(f"Can Swap Token1 to Token0: {diagnosis['swap_path_info']['one_to_zero']['can_swap']}")
        
    except Exception as e:
        print(f"Diagnosis failed: {str(e)}")

if __name__ == "__main__":
    main()