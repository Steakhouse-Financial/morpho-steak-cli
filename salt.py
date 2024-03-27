#        address predictedAddress = address(uint160(uint(keccak256(abi.encodePacked(
#            bytes1(0xff),
#            address(this),
#            salt,
#            keccak256(abi.encodePacked(
#                type(D).creationCode,
#                abi.encode(arg)
#            ))
#        )))));


# keccak256(abi.encodePacked(
#                type(D).creationCode,
#                abi.encode(arg)*/

from web3 import Web3
from eth_abi import encode
from random import randbytes
import web3

print(web3.__version__)


def predict_create2_address(creator_address, salt, bytecode):
    """
    Predicts the address of a contract created using CREATE2.

    Args:
        creator_address: The address of the contract creator (bytes object).
        salt: The salt used for CREATE2 (bytes object).
        bytecode: The bytecode of the contract to be deployed (bytes object).

    Returns:
        The predicted address of the deployed contract (bytes object).
    """
    abi_encoded = Web3.solidity_keccak(
        ["bytes1", "address", "bytes32", "bytes32"],
        ["0xff", creator_address, salt, bytecode],
    )
    return abi_encoded[12:].hex()  # trunc to address


# Example usage
creator_address = Web3.to_checksum_address("0xa9c3d3a366466fa809d1ae982fb2c46e5fc41101")
salt = "0xfd08ed5c53c964ac65f7c772d292887e265a63a402d5c81cb3e558763af3953d"
code = open("bytecode.txt", "r").read()
bytecode = bytes.fromhex(code[2:])
morpho = Web3.to_checksum_address("0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb")
owner = Web3.to_checksum_address("0x255c7705e8BB334DfCae438197f7C4297988085a")
timelock = 86400
asset = Web3.to_checksum_address("0x2260fac5e5542a773aa44fbcfedf7c193bc2c599")
name = "Steakhouse WBTC"
symbol = "steakWBTC"

constructor_args = [owner, morpho, timelock, asset, name, symbol]

print("ARGS")
print(
    encode(
        ["address", "address", "uint256", "address", "string", "string"],
        constructor_args,
    ).hex()
)


#             keccak256(abi.encodePacked(
#                type(D).creationCode,
#                abi.encode(arg)
params = encode(
    ["address", "address", "uint256", "address", "string", "string"], constructor_args
)
print()
print(params.hex())
print()


export = encode(["bytes", "bytes"], [bytecode, params])
print()

dacode = Web3.solidity_keccak(["bytes32", "bytes32"], [bytecode, params])
print(dacode.hex())


predicted_address = predict_create2_address(creator_address, salt, dacode)
print(f"Predicted contract address: {predicted_address}")


def find(start, creator_address, bytecode):
    ok = False
    while ok is False:
        salt = randbytes(32)
        address = predict_create2_address(creator_address, salt, dacode)
        if address[2:].startswith(start):
            print(f"salt {salt.hex()} => {address}")
            ok = True


find("beef", creator_address, dacode)
