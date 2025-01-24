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
            with open("./abis/factory_abi.json", "r") as abi_json:
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
        
        with open("./abis/pool_abi.json", "r") as f:
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
        with open("./abis/nft_manager_abi.json", "r") as f:
            nft_manager_abi = json.load(f)
        
        # Initialize the nft_manager V3
        # Get pool fee instead of hardcoding it
        with open("./abis/pool_abi.json", "r") as f:
            pool_abi = json.load(f)
        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
        pool_fee = pool.functions.fee().call()

        # Convert addresses to checksum format
        nft_manager_address = Web3.to_checksum_address(self.nft_manager_address)
        nft_manager = self.w3.eth.contract(address= nft_manager_address, abi = nft_manager_abi)
        token0_address = Web3.to_checksum_address(self.token0_address)
        token1_address = Web3.to_checksum_address(self.token1_address)
        # Approve the spending of token 0 and 1 on the nft manager
        with open("./abis/ERC20_abi.json", "r") as f:
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
        
        
        try:
                    # Load ABIs
            with open("./abis/swaprouterv3_abi.json", "r") as f:
                router_abi = json.load(f)
            with open("./abis/pool_abi.json", "r") as f:
                pool_abi = json.load(f)
            with open("./abis/ERC20_abi.json", "r") as f:
                erc20_abi = json.load(f)
            
            # Contract setup
            router = self.w3.eth.contract(address=Web3.to_checksum_address(router_address), abi=router_abi)
            token0 = self.w3.eth.contract(address=Web3.to_checksum_address(self.token0_address), abi=erc20_abi)
            
            # Get pool fee
            pool = self.w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
            fee = pool.functions.fee().call()
            
            # Approve router
            approve_tx = token0.functions.approve(router_address, amount_in).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000
            })
            signed_tx = self.w3.eth.account.sign_transaction(approve_tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            print("Token Approved")

            # Encode path correctly: address + fee + address
            encoded_path = Web3.to_bytes(hexstr=self.token0_address) + \
               fee.to_bytes(3, 'big') + \
               Web3.to_bytes(hexstr=self.token1_address)

            params = {
                'path': encoded_path,
                'recipient': self.account.address,
                'deadline': self.w3.eth.get_block('latest')['timestamp'] + 1200,
                'amountIn': amount_in,
                'amountOutMinimum': 0
            }
            print("path is: ", encoded_path)
            print("params are: ", params)

            # Execute swap
            swap_tx = router.functions.exactInput(params).build_transaction({
                'from': self.account.address,
                'value': 0,
                'gas': 500000,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gasPrice': self.w3.eth.gas_price
            })

            signed_tx = self.w3.eth.account.sign_transaction(swap_tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt['status'] != 1:
                raise RuntimeError(f"Swap failed: {tx_hash.hex()}")

            return tx_hash.hex()

        except Exception as e:
            raise RuntimeError(f"Swap failed: {str(e)}")

    def swap_tokens_alternative(self, router_address: str, pool_address: str, amount_in: int):
        
        
        try:
            # Load ABIs
            with open("./abis/swaprouterv3_abi.json", "r") as f:
                router_abi = json.load(f)
            with open("./abis/pool_abi.json", "r") as f:
                pool_abi = json.load(f)
            with open("./abis/ERC20_abi.json", "r") as f:
                erc20_abi = json.load(f)
            
            # Contract setup
            router = self.w3.eth.contract(address=Web3.to_checksum_address(router_address), abi=router_abi)
            token1 = self.w3.eth.contract(address=Web3.to_checksum_address(self.token1_address), abi=erc20_abi)
            
            # Get pool fee
            pool = self.w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
            fee = pool.functions.fee().call()
            
            # Approve router
            approve_tx = token1.functions.approve(router_address, amount_in).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 100000
            })
            signed_tx = self.w3.eth.account.sign_transaction(approve_tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            print("Token Approved")

            params = {
                "tokenIn": self.token1_address,
                "tokenOut": self.token0_address,
                "fee": fee,
                'recipient': self.account.address,
                'deadline': self.w3.eth.get_block('latest')['timestamp'] + 1200,
                'amountIn': amount_in,
                'amountOutMinimum': 0,
                'sqrtPriceLimitX96': 0
            }

            print("params are: ", params)

            # Execute swap
            swap_tx = router.functions.exactInputSingle(params).build_transaction({
                'from': self.account.address,
                'value': 0,
                'gas': 500000,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gasPrice': self.w3.eth.gas_price
            })

            signed_tx = self.w3.eth.account.sign_transaction(swap_tx, self.account.key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt['status'] != 1:
                raise RuntimeError(f"Swap failed: {tx_hash.hex()}")

            return tx_hash.hex()

        except Exception as e:
            raise RuntimeError(f"Swap failed: {str(e)}")
        
    def query_event_logs(self, pool_address: str):
        with open('./abis/pool_abi.json', 'r') as f:
            pool_abi = json.load(f)

        pool = self.w3.eth.contract(address = pool_address, abi = pool_abi)
        
        # get the event names available in the contract
        available_log_names = []
        for entry in pool_abi:
            if entry['type'] == 'event':
                available_log_names.append(entry['name'])
        #print(available_log_names)

        # Get earliest block involved with my contract (the block when the contract was deployed):
        """
        # Get contract deployment block -> to adjust later
        deploy_block = self.w3.eth.get_transaction_receipt(
            self.w3.eth.get_transaction_by_block(
            self.w3.eth.get_transaction_count(pool_address, "earliest"),
            0
            )["hash"]
            )["blockNumber"]
        """

        # manual: know the initialize block number via block explorer
        initialization_block = 9593217

        # Get latest block (the one of right now or close to it)
        latest_block = self.w3.eth.block_number
        
        event_logs = {}
        for entry in pool_abi:
            if entry['type'] == 'event' and entry['name'] in ['Swap', 'Initialize', 'Mint']:
                event_name = entry['name']
                # getattr() helps when you have function names stored in variables/strings and need to call them.
                event = getattr(pool.events, event_name) # learning: good python method to get function names that match functions as strings in my lists or dic data structs.
                #logs = event.get_logs(from_block=0, to_block=latest_block) -> error Error when setting up the Pool: 413 Client Error: Request Entity Too Large for url: https://bartio.rpc.berachain.com/
                logs = event.get_logs(from_block=initialization_block, to_block = latest_block)
                event_logs[event_name] = logs
                
        return event_logs
        
    def query_single_event(self, pool_address: str, event_name: str):
        with open('./abis/pool_abi.json', 'r') as f:
            pool_abi = json.load(f)

        pool = self.w3.eth.contract(address=pool_address, abi=pool_abi)
        start_block = 9593217
        end_block = self.w3.eth.block_number
        
        event = getattr(pool.events, event_name)
        try:
            logs = event.get_logs(from_block=start_block, to_block=end_block)
            print(f"Found {len(logs)} events")
            return logs
        except Exception as e:
            print(f"Error: {e}")

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
    router_address = Web3.to_checksum_address('0x66e8f0cf851ce9be42a2f133a8851bc6b70b9ebd')    
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

        print("Trying to swap tokens...")        

        amount_to_swap = 500 * 10**6  # Swap 500 tokens
        print(f'trying to swap {amount_to_swap} tokens')
        # swaps usdt (token 0) for usdc (token 1)
        #swap_tx = setup.swap_tokens(router_address,pool_address, amount_to_swap)
        # uses usdc for usdt with a different swap function on iswaprouter
        #swap_tx = setup.swap_tokens_alternative(router_address, pool_address,amount_to_swap)
        #print(f"Swap successful! Transaction: {swap_tx}")

        # get events for pool
        #logs = setup.query_event_logs(pool_address) -> exceed rpc limit apparently
        logs = setup.query_single_event(pool_address, 'Swap')
        print(logs)

    except Exception as e: 
        print(f"Error when setting up the Pool: {e}")

# Run the function
if __name__ == "__main__":
    main()