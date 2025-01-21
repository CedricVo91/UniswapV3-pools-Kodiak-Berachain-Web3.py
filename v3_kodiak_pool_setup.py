from web3 import Web3
from eth_account import Account
import json
import os
from typing import Optional # useful to declare types for web3 object types

# Define a class to setup Pool initialization on Kodiak V3
class KodiakV3Setup:
    """
    Setup everything to then run methods to:
    - Initializes a Kodiak V3 Pool on Bartio testnet with two of our already deployed MockTokens
    - Fund the Pool with our mock tokens 
    - Use the pool to implement the Price Attack!
    """

    def __init__(self, token1_address: str, token2_address: str, factory_address: str, rpc_url: str):
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

    def set_signer(self, private_key: str):
        """Set up the account that will sign transactions"""
        self.account = Account.from_key(private_key)

    def create_pool(self, chain_id) -> str:
        # Set fee
        fee = 100 # 0.01% for stable coin and ensuring minimal slippage 
        
        # check if pool already exists to avoid recreating it when we run our script for testing purposes and save gas
        existing_pool = self.factory.functions.getPool(self.token0_address, self.token1_address, fee).call()
        if existing_pool != "0x0000000000000000000000000000000000000000": # use the zero address to check if pool is not instantiated yet
            raise ValueError("Pool already exists at: ", existing_pool)

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
            
            return tx_hash.hex()  # Return transaction hash as hex string
        
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
    def initialize_V3pool():
        pass
# Main function to run the script
def main():
    rpc_url = os.environ.get("RPC_URL")
    private_key = os.environ.get("PK") # might do that via entering into terminal for security reasons
    #print("rpc url: ", rpc_url)

    if not rpc_url or not private_key:
        raise ValueError("Missing RPC_URL or PK environment variables")
    


    mockUSD = "0xc3D7F1F91a77618C959f8114422af4b3d70b2B4C"
    mockUSDT = "0x3E6Ed0430B872599BC7b2E1c9833B8f1552b5518"
    UniswapV3FactoryKodiak = "0x217Cd80795EfCa5025d47023da5c03a24fA95356"
    chain_id = 80084
    
    
    try:
        setup = KodiakV3Setup(mockUSD, mockUSDT, UniswapV3FactoryKodiak, rpc_url)
        setup.set_signer(private_key)
        print("Setup successful!")
        print("Trying to create Pool...")
        setup.create_pool(chain_id)
    
    except Exception as e: 
        print(f"Error when setting up the Pool: {e}")

# Run the function
if __name__ == "__main__":
    main()