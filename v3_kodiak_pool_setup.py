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

    def __init__(self, address_token1: str, address_token2: str, factory_address: str, rpc_url: str):
        ## Golden Rule for good class design -> Initialization Clarity: The init method should establish everything the class needs to function. 
        ## How would you modify the class to make it impossible to use it incorrectly?
        ## I should list all the attributes this KodiakV3Setup class would need <=> What is needed to setup a v3 pool on kodiak?
        
        # mocktoken addressses 
        # factory addresses 
        # facotry abis 
        # first a web3 instance to connect to the remote rpc url from bartio 
        self.mock_token1_address = address_token1
        self.mock_token2_address = address_token2
        self.factory_address = factory_address
        # initialize a remote connection
        try:
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        except Exception as e:
            raise ConnectionError("failed to connect: ", e)  

        with open("abi.json", "r") as abi_json:
            abi = json.load(abi_json)

        self.kodiak_factory_instance = self.w3.eth.contract(address=self.factory_address, abi = abi)
    
    def deploy_pool(self):
        #self.kodiak_factory_instance.function_todeploy_(self.mock_token1_address, self.mock_token2_address,...)          

 # I need to connect to a remote node i.e. RPC URL 
"""
    def connect_to_remote_node(self, rpc_url: str) -> Optional[Web3]:
        w3 = Web3(Web3.HTTPProvider(rpc_url)) # do I need here a self.Web3? not really as its more of a helper function
        if w3.is_connected:
            return w3
        else:
            raise ConnectionError(f"Failed to connect to {w3}") # better to return some kind of error message
    
 # I need to (0) initialize an Uniswap contract instance
    def setup_contract_instance(self, w3: Optional[Web3]): #figure out what w3 type is to be entered
        # read the contract abi
        with open("abi.json", "r") as abi_json:
            abi = json.load(abi_json) # json load expects a file object, not a string!

        # initialize the contract instance
        contract_instance = w3.eth.contract(address = self.factory_address, abi = abi)
        return contract_instance
"""              
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

    mockUSD = "0xc3D7F1F91a77618C959f8114422af4b3d70b2B4C"
    mockUSDT = "0x3E6Ed0430B872599BC7b2E1c9833B8f1552b5518"
    UniswapV3FactoryKodiak = "0x217Cd80795EfCa5025d47023da5c03a24fA95356"
    
    setup = KodiakV3Setup(mockUSD, mockUSDT, UniswapV3FactoryKodiak)
    
    try:
        print("trying to connect to w3 remote url...")
        w3 = setup.connect_to_remote_node(rpc_url)
        Kodiak_V3_Factory = setup.setup_contract_instance(w3)
        print("Kodiak V3 Factory contract successfully instantiated with address: ", Kodiak_V3_Factory.address) 
    
    except Exception as e: 
        print(f"Error when setting up the Pool: {e}")

# Run the function
if __name__ == "__main__":
    main()