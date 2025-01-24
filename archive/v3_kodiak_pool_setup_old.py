from web3 import Web3
from eth_account import Account
import json
from dotenv import load_dotenv
import os
from typing import Optional # useful to declare types for web3 object types
import math

# Define a class to setup Pool initialization on Kodiak V3
class KodiakV3Setup:
    """
    Setup everything to then run methods to:
    - Initializes a Kodiak V3 Pool on Bartio testnet with two of our already deployed MockTokens
    - Fund the Pool with our mock tokens 
    - Use the pool to implement the Price Attack!
    """

    def __init__(self, token1_address: str, token2_address: str, factory_address: str, rpc_url: str, nft_manager_address: str):
        ## Golden Rule for good class design -> Initialization Clarity: The init method should establish everything the class needs to function. 
        ## How would you modify the class to make it impossible to use it incorrectly?
        ## I should list all the attributes this KodiakV3Setup class would need <=> What is needed to setup a v3 pool on kodiak?
        
        # store addresses in sorted order as V3 transactions often fail due to sorting issues
        self.token0_address, self.token1_address  = sorted([token1_address, token2_address])
        self.factory_address = factory_address
        
        # initialize a web3 connection
        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        except Exception as e:
            raise ConnectionError("failed to connect: ", e)  

        # load factory ABI and create contract instance
        try:
            with open("factory_abi.json", "r") as abi_json:
                abi = json.load(abi_json)

            self.factory = self.w3.eth.contract(address=self.factory_address, abi = abi)
        
        except FileNotFoundError:
            raise FileNotFoundError("factory_abi.json not found")
        
        except json.JSONDecodeError:
            raise ValueError("Invalid ABI JSON format")

        # nft_manager_address so we can add liquidity to our pool
        self.nft_manager_address = nft_manager_address

    def set_signer(self, private_key: str):
        """Set up the account that will sign transactions"""
        self.account = Account.from_key(private_key)

    def create_pool(self, chain_id) -> str:
        # Set fee
        fee = 100 # 0.01% for stable coin and ensuring minimal slippage 
        
        # check if pool already exists to avoid recreating it when we run our script for testing purposes and save gas
        existing_pool_address = self.factory.functions.getPool(self.token0_address, self.token1_address, fee).call()
        if existing_pool_address != "0x0000000000000000000000000000000000000000": # use the zero address to check if pool is not instantiated yet
            print(f"Pool already exists at: {existing_pool_address}")
            return existing_pool_address

        try: 
            # Estimate gas and add buffer
            gas_estimate = self.factory.functions.createPool(self.token0_address, self.token1_address, fee).estimate_gas({'from': self.account.address})
            gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
        
            # build a transaction s a pool creation changes the state of the blockchain
            tx = self.factory.functions.createPool(self.token0_address, self.token1_address, fee).build_transaction({'from':self.account.address, 'chainId':chain_id,'gas':gas_estimate,'gasPrice': self.w3.eth.gas_price, 'nonce': self.w3.eth.get_transaction_count(self.account.address)})
        
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key = self.account.key)
        
            # Broadcast the transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            print(tx_receipt)
            # Check if transaction was successful
            if tx_receipt['status'] != 1:
                raise RuntimeError("Pool creation failed")
            
            # get pool address out of transaction
            # Get pool address from event logs
            pool_created_event = self.factory.events.PoolCreated().process_receipt(tx_receipt)[0]
            pool_address = pool_created_event['args']['pool']

            return pool_address  # Return transaction hash as hex string
        
        except Exception as e:
            raise RuntimeError(f"Failed to create pool: {str(e)}")
            
     # I need to (1) build transaction -> A transaction that builds a pool from v3 uniswap pool 
        #txn = contract_instance.functions._functionName_().build_transaction({'chain_id':,'gas':,'maxFeePerGas':, 'maxPriorityFeePerGas':, 'nonce':})
        #txn = ''
    # I need to (2) sign the transaction -> w3.eth.account.sign_transaction()
        #signed_txn = w3.eth.account.sign_transaction(txn, private_key = self.private_key)
 
    # I need to (3) broadcast the transaction with send_raw_transaction()    
        #w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        #tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        #return w3.to_hex(w3.keccak(signed_txn.raw_transaction)) # should give me back the hash of the transaction
    
    # in V3 we first have to initialize the pool! Important difference to v2
    def initialize_V3pool(self, pool_address: str):
        """
        Initialize a newly created pool with 1:1 price for stablecoins
        """
        # For 1:1 price (stablecoins):
        # 1. Start with price = 1.0
        # 2. Take square root: √1 = 1.0
        # 3. Multiply by 2^96 for Q64.96 encoding
        INITIAL_SQRTPRICE = 1 * 2**96  # = 79228162514264337593543950336
        
        with open("pool_abi.json", "r") as f:
            pool_abi = json.load(f)
        pool = self.w3.eth.contract(address=pool_address, abi = pool_abi)

        # Check if pool is already initialized
        try:
            slot0 = pool.functions.slot0().call()
            current_sqrt_price = slot0[0]
            print(f"Pool already initialized with sqrt price: {current_sqrt_price}")
            return None  
        
        # Pool is not yet initialized 
        except Exception:
            # send transaction to initialize the pool
            try:
                nonce = self.w3.eth.get_transaction_count(self.account.address)

                # build transaction
                tx = pool.functions.initialize(INITIAL_SQRTPRICE).build_transaction({'from': self.account.address, 'nonce': nonce, 'gas': 200000})

                # Sign and send
                signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
                # Wait for confirmation
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
                if tx_receipt['status'] != 1:
                    raise RuntimeError("Pool initialization failed")
                
                return tx_hash.hex()

            except Exception as e:
                raise RuntimeError(f"failed to initialize pool: {str(e)}")    

    def add_full_range_liquidity(self, pool_address, amount0, amount1):
        
        # Set maxmimal tick range to mimick v2 pool
        # Docs: Computes sqrt price for ticks of size 1.0001, i.e. sqrt(1.0001^tick) as fixed point Q64.96 numbers. 
        # Supports prices between 2-128 and 2128
        # These are the actual values from TickMath library
        price_step = 1.0001
        min_allowed_price = 2**(-128)
        max_allowed_price = 2**128

        # in the mint function the min and max ticks must be of type int!
        MIN_TICK = int(math.log(min_allowed_price) / math.log(price_step)) # TickMath.MIN_TICK -> they represent how many steps we need to get to the value needed. in our case the max and min value given by the docs
        MAX_TICK = int(math.log(max_allowed_price) / math.log(price_step)) # TickMath.MAX_TICK
        
        MIN_TICK = -887272
        MAX_TICK = 887272 
        #initialize the nft_manager contract on Uniswap V3
        with open("nft_manager_abi.json", "r") as f:
            nft_manager_abi = json.load(f)
        
        # Initialize the nft_manager V3
        # Get pool fee instead of hardcoding it
        with open("pool_abi.json", "r") as f:
            pool_abi = json.load(f)
        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
        pool_fee = pool.functions.fee().call()

        # Convert addresses to checksum format
        nft_manager_address = Web3.to_checksum_address(self.nft_manager_address)
        nft_manager = self.w3.eth.contract(address= nft_manager_address, abi = nft_manager_abi)
        token0_address = Web3.to_checksum_address(self.token0_address)
        token1_address = Web3.to_checksum_address(self.token1_address)
        # Approve the spending of token 0 and 1 on the nft manager
        with open("ERC20_abi.json", "r") as f:
            erc20_abi = json.load(f)
        
        try:
            for token_addr, amount in [(token0_address, amount0), (token1_address, amount1)]:
                token = self.w3.eth.contract(address=token_addr, abi=erc20_abi)
                tx = token.functions.approve(nft_manager_address, amount).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000
                })
                signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                self.w3.eth.wait_for_transaction_receipt(tx_hash)
                print(f"Approved token {token_addr}")
            
            print("both tokens approved!")
            
        except Exception as e:
            raise RuntimeError("couldnt approve tokens: ",e)

        try: 
            tx = nft_manager.functions.mint({
            'token0': token0_address,
            'token1': token1_address,
            'fee': pool_fee,
            'tickLower': MIN_TICK,
            'tickUpper': MAX_TICK,
            'amount0Desired': amount0,
            'amount1Desired': amount1,
            'amount0Min': 0,
            'amount1Min': 0,
            'recipient': self.account.address,
            'deadline': self.w3.eth.get_block('latest')['timestamp'] + 1200 }).build_transaction({'from': self.account.address,'gas': 1000000,'gasPrice': self.w3.eth.gas_price,'nonce': self.w3.eth.get_transaction_count(self.account.address)})

             # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
            # Wait for confirmation
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
            if tx_receipt['status'] != 1:
                raise RuntimeError("Failed to add liquidity")
            
            # After minting liquidity, add:
            mint_event = nft_manager.events.IncreaseLiquidity().process_receipt(tx_receipt)[0]
            position_id = mint_event['args']['tokenId']
            print(f"Position ID: {position_id}")

            # After your add_full_range_liquidity succeeds:
            pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
            position = nft_manager.functions.positions(position_id).call()
            print(f"Position ticks: {position[5]} to {position[6]}")
            print(f"Position liquidity: {position[7]}")

            tick_lower_info = pool.functions.ticks(position[5]).call()
            tick_upper_info = pool.functions.ticks(position[6]).call()
            print(f"Tick initialization: Lower={tick_lower_info[0]>0}, Upper={tick_upper_info[0]>0}")

            return tx_hash.hex()
        
        except Exception as e:
            raise RuntimeError(f"failed to add liquidity: {str(e)}") 
                
    def swap_tokens(self, router_address: str, pool_address: str, amount_in: int):
        """
        Swap tokens in the pool
        amount_in: Amount to swap in base units (e.g., 500 * 10**6 for 500 USDC)
        """
        # Load pool ABI and create contract instance
        with open("swaprouterv3_abi.json", "r") as f:
            swap_router_abi = json.load(f)
        swap_router = self.w3.eth.contract(address=router_address, abi=swap_router_abi)


        # First approve the pool to spend token0
        with open("ERC20_abi.json", "r") as f:
            erc20_abi = json.load(f)
        
        # token 0 is usdt according to block explorer
        token0 = self.w3.eth.contract(address=self.token0_address, abi=erc20_abi)
        token0_decimals = self.get_token_decimals(self.token0_address)
        print(f'Token0 has address: {self.token0_address}')
        print(f"Token0 decimals: {token0_decimals}")
        
        try:
            # Approve pool to spend token0
            approve_tx = token0.functions.approve(
                router_address,
                amount_in
            ).build_transaction({
                'from': self.account.address,
                'gas': 100000,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(approve_tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"Approved router to spend token0")
        
        except Exception as e:
            raise RuntimeError("failed to approve router to spend token0")

        # Verify fee tier
        with open("pool_abi.json") as f:
            pool_abi = json.load(f)
        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
        fee = pool.functions.fee().call()
        print(f"Pool fee tier: {fee}")
        
        # Get token decimals
        token0_decimals = self.get_token_decimals(self.token0_address)
        print(f'Token0 has address: {self.token0_address}')
        print(f'Token1 has address: {self.token1_address}')
        
        # get deadline
        # Current timestamp plus 20 minutes for deadline
        deadline = self.w3.eth.get_block('latest')['timestamp'] + 1200
               
         # Prepare swap parameters
        params = {
            'tokenIn': self.token0_address,
            'tokenOut': self.token1_address,
            'fee': fee,
            'recipient': self.account.address,
            'deadline': deadline,
            'amountIn': amount_in,
            'amountOutMinimum': 0,  # In production, calculate this using an oracle
            'sqrtPriceLimitX96': 0  # 0 means no limit
        }

        # Estimate gas for the swap
        gas_estimate = swap_router.functions.exactInputSingle(params).estimate_gas({
            'from': self.account.address
        })
        print(f"Estimated gas: {gas_estimate}")
        
        try:
            # Perform swap
            # Build swap transaction
            swap_tx = swap_router.functions.exactInputSingle(params).build_transaction({
                'from': self.account.address,
                'gas': int(gas_estimate * 1.5),  # Add 50% buffer
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gasPrice': self.w3.eth.gas_price
            })
            # Sign and send transaction
            signed_tx = self.w3.eth.account.sign_transaction(swap_tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] != 1:
                # If transaction fails, try to get more error details
                tx = self.w3.eth.get_transaction(tx_hash)
                try:    
                    result = self.w3.eth.call({
                        'to': tx['to'],
                        'from': tx['from'],
                        'data': tx['input'],
                        'value': tx['value'],
                        'gas': tx['gas'],
                        'gasPrice': tx['gasPrice']
                    },
                    receipt['blockNumber'] - 1
                    )
                    print(f"Call result: {result.hex()}")

                except Exception as e:
                    print(f"Detailed error: {str(e)}") 

            return tx_hash.hex()         

        except Exception as e:
            raise RuntimeError("Swap failed with error: ", e)

    def check_token_balance(self, token_address):
        """Check token balance for the account"""
        with open("ERC20_abi.json", "r") as f:
            erc20_abi = json.load(f)
        
        token = self.w3.eth.contract(address=token_address, abi=erc20_abi)
        balance = token.functions.balanceOf(self.account.address).call()
        return balance
    
    def check_pool_state(self, pool_address):
        """Check pool state before swap"""
        with open("pool_abi.json", "r") as f:
            pool_abi = json.load(f)
        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
        
        liquidity = pool.functions.liquidity().call()
        slot0 = pool.functions.slot0().call()
        
        print(f"Pool state:")
        print(f"- Liquidity: {liquidity}")
        print(f"- Current sqrt price: {slot0[0]}")
        print(f"- Current tick: {slot0[1]}")
        print(f"- Pool unlocked: {slot0[6]}")
        
        return liquidity > 0
    
        # Add this check before swapping
    def verify_pool_fee(self, pool_address):
        """Verify pool fee tier"""
        with open("pool_abi.json", "r") as f:
            pool_abi = json.load(f)
        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
        fee = pool.functions.fee().call()
        print(f"Pool fee tier: {fee}")
        return fee
    
    def get_token_decimals(self, token_address):
        """Get token decimals"""
        with open("ERC20_abi.json", "r") as f:
            erc20_abi = json.load(f)
        token = self.w3.eth.contract(address=token_address, abi=erc20_abi)
        return token.functions.decimals().call()

# Main function to run the script
def main():
    load_dotenv()
    rpc_url = os.environ.get("RPC_URL")
    private_key = os.environ.get("PK") # might do that via entering into terminal for security reasons
    #print("rpc url: ", rpc_url)

    if not rpc_url or not private_key:
        raise ValueError("Missing RPC_URL or PK environment variables")
    


    mockUSD = "0xc3D7F1F91a77618C959f8114422af4b3d70b2B4C"
    mockUSDT = "0x3E6Ed0430B872599BC7b2E1c9833B8f1552b5518"
    UniswapV3FactoryKodiak = "0x217Cd80795EfCa5025d47023da5c03a24fA95356"
    chain_id = 80084
    nft_manager_address = "0xc0568c6e9d5404124c8aa9efd955f3f14c8e64a6"
    router_address = '0x496e305C03909ae382974cAcA4c580E1BF32afBE'
    
    try:
        setup = KodiakV3Setup(mockUSD, mockUSDT, UniswapV3FactoryKodiak, rpc_url, nft_manager_address)
        setup.set_signer(private_key)
        print("Setup successful!")
        print("Trying to create Pool...")
        pool_address = setup.create_pool(chain_id)
        print("Pool at address: ", pool_address)
        print("tryin to initialize pool with 1:1 price: ")
        init_tx = setup.initialize_V3pool(pool_address) # d56fc11ce09e050c9a346205cbe5cc968e7e25faa29d75038ec12bf184a879d1
        print(init_tx)

        #print("Trying to fund pool...")
        #amount0 = 1000 * 10**6  # 1000 USDC 
        #amount1 = 1000 * 10**6  # 1000 USDT 
        #tx_hash = setup.add_full_range_liquidity(pool_address, amount0, amount1)
        #print(tx_hash)
        #print("funded pool successfully")

        # check token ordering...
        print("Trying to swap tokens...")
        
        # Check balance before swap
        token0_balance = setup.check_token_balance(mockUSDT)
        print(f"Token0 balance: {token0_balance / 10**6} tokens")

        if setup.check_pool_state(pool_address):
            print("Pool state is valid, proceeding with swap...")
            amount_to_swap = 500 * 10**6  # Swap 500 tokens
            print(f'trying to swap {amount_to_swap} tokens')
            swap_tx = setup.swap_tokens(router_address,pool_address, amount_to_swap)
            print(f"Swap successful! Transaction: {swap_tx}")
        else:
            print("Pool state invalid - please add liquidity first")
    
    except Exception as e: 
        print(f"Error when setting up the Pool: {e}")

# Run the function
if __name__ == "__main__":
    main()