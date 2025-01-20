from web3 import Web3
from eth_account import Account
import json
import os

# Define a class to setup Pool initialization on Kodiak V3
class KodiakV3Setup:
    def __init__(self, private_key: str):
        private_key = os.environ.get("PK")

 # I need to connect to a remote node i.e. RPC URL 
    def connect_to_remote_node(self, rpc_url: str):
        rpc_url = os.environ.get(rpc_url)
        w3 = self.Web3(Web3.HTTPProvider(rpc_url))
        if w3.is_connected() == True:
            return w3
        else:
            raise ConnectionError(f"Failed to connect to {w3}") # better to return some kind of error message
    
 # I need to (0) initialize an Uniswap contract instance
    def setup_contract_instance(self, w3, address): #figure out what w3 type is to be entered
        # read the contract abi
        with open("abi.json", "r") as abi_json:
            abi = json.load(abi_json) # json load expects a file object, not a string!

        # initialize the contract instance
        contract_instance = w3.eth.contract(address = address, abi = abi)
        
              
 # I need to (1) build transaction -> A transaction that builds a pool from v3 uniswap pool 
        #txn = contract_instance.functions._functionName_().build_transaction({'chain_id':,'gas':,'maxFeePerGas':, 'maxPriorityFeePerGas':, 'nonce':})
        txn = ''
 # I need to (2) sign the transaction -> w3.eth.account.sign_transaction()
        signed_txn = w3.eth.account.sign_transaction(txn, private_key = self.private_key)
 
 # I need to (3) broadcast the transaction with send_raw_transaction()    
        w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        return w3.to_hex(w3.keccak(signed_txn.raw_transaction)) # should give me back the hash of the transaction

# Main function to run the script
def main():
    private_key = "" # might do that via entering into terminal for security reasons
    #rpc_url = ""

    setup = KodiakV3Setup(private_key)
    
    try:
        pass

    except Exception as e: 
        print(f"Error when setting up the Pool: {e}")

# Run the function
if __name__ == "__main__":
    main()