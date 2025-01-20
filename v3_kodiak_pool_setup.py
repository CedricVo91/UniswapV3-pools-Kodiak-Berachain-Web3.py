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

    def deploy_pool(self):
        #self.kodiak_factory_instance.function_todeploy_(self.mock_token1_address, self.mock_token2_address,...)
        pass          
     
     # I need to (1) build transaction -> A transaction that builds a pool from v3 uniswap pool 
        #txn = contract_instance.functions._functionName_().build_transaction({'chain_id':,'gas':,'maxFeePerGas':, 'maxPriorityFeePerGas':, 'nonce':})
        #txn = ''
    # I need to (2) sign the transaction -> w3.eth.account.sign_transaction()
        #signed_txn = w3.eth.account.sign_transaction(txn, private_key = self.private_key)
 
    # I need to (3) broadcast the transaction with send_raw_transaction()    
        #w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        #tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        #return w3.to_hex(w3.keccak(signed_txn.raw_transaction)) # should give me back the hash of the transaction

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
    
    
    
    try:
        setup = KodiakV3Setup(mockUSD, mockUSDT, UniswapV3FactoryKodiak, rpc_url)
        setup.set_signer(private_key)
        print("Setup successful!")
    
    except Exception as e: 
        print(f"Error when setting up the Pool: {e}")

# Run the function
if __name__ == "__main__":
    main()