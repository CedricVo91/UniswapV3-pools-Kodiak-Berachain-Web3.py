import { JsonRpcProvider, toUtf8String, TransactionRequest } from "ethers";

// import { ErrorDecoder } from "ethers-decode-error";
// import type { DecodedError } from "ethers-decode-error";

// import { OnDemandOracleUpgradeable__factory } from "../src";

const RPC_URL = "https://bartio.rpc.berachain.com";
// const RPC_URL = "https://xlayerrpc.okx.com";
const HASH = "0x8ccc4394d9fa4a9e596d87b003c531e05a43a2c22a8a8d2cf02aae6ed10c8162";

async function run() {
  const provider = new JsonRpcProvider(RPC_URL);
  const tx = await provider.getTransaction(HASH);
  if (!tx) {
    return;
  }
  // const tx = await receipt?.();
  // await provider.call()
  const request: TransactionRequest = {
    to: tx.to,
    from: tx.from,
    nonce: tx.nonce,
    gasLimit: tx.gasLimit,
    gasPrice: tx.gasPrice,
    data: tx.data,
    value: tx.value,
    chainId: tx.chainId,
    type: tx.type ?? undefined,
    accessList: tx.accessList,
    blockTag: tx.blockNumber!,
  };

  // const abi = OnDemandOracleUpgradeable__factory.createInterface();
  // const errorDecoder = ErrorDecoder.create([abi]);

  try {
    const response = await provider.call(request);

    const toDecode = "0x" + (response.substring(138) || "");
    console.log(toDecode);
    console.log(toUtf8String(toDecode));
  } catch (e) {
    console.log(e);
    // const decodedError = await errorDecoder.decode(e);
    // const reason = customReasonMapper(decodedError)
    // console.log(decodedError);
    console.log(e);
  }
}

run().then();