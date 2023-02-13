#    Copyright Frank V. Castellucci
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#        http://www.apache.org/licenses/LICENSE-2.0
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

# -*- coding: utf-8 -*-

"""Sui BCS Conversions [EXPERIMENTAL]."""

import base64
import binascii
from typing import Any, Union
import canoser
from pysui.sui.sui_types.address import SuiAddress
from pysui.sui.sui_utils import hexstring_to_list, b58str_to_list, b64str_to_list
from pysui.sui.sui_clients.common import SuiRpcResult
from pysui.sui.sui_txresults.common import GenericRef
from pysui.sui.sui_builders.exec_builders import (
    _MoveCallTransactionBuilder,
)

from pysui.sui.sui_clients.sync_client import SuiClient as SyncClient
from pysui.sui.sui_types.scalars import ObjectID


_BCS_ADDRESS_LENGTH: int = 20
_BCS_DIGEST_LENGTH: int = 32
_TKIND_INDEX: int = 0
_SUB_TKIND_INDEX: int = 1
_GAS_AND_BUDGET_BYTE_OFFSET: int = -97


def tkind_from_result(indata: SuiRpcResult) -> Union[str, SuiRpcResult]:
    """tkind_from_result Return a BCS serialized kind as base64 encoded string.

    :param indata: _description_
    :type indata: SuiRpcResult
    :rtype: str
    """
    if indata.is_ok():
        _, no_sign_tx_bytes = indata.result_data
        return base64.b16encode(base64.b64decode(no_sign_tx_bytes)[:-_GAS_AND_BUDGET_BYTE_OFFSET]).decode()
    return indata


class BCSAddress(canoser.Struct):
    """BCSAddress Represents a Sui Address or ObjectID in int list format.

    :ivar _fields: Contains the Address BCS descriptor
    :ivar type _fields: list[int]
    """

    _fields = [("Address", canoser.ArrayT(canoser.Uint8, _BCS_ADDRESS_LENGTH, False))]

    def to_str(self) -> str:
        """."""
        return binascii.hexlify(bytes(getattr(self, "Address"))).decode()

    def to_address_str(self) -> str:
        """."""
        return f"0x{self.to_str()}"

    def to_sui_address(self) -> SuiAddress:
        """."""
        return SuiAddress(self.to_address_str())

    @classmethod
    def from_sui_address(cls, indata: SuiAddress) -> "BCSAddress":
        """."""
        return cls(hexstring_to_list(indata.address))

    @classmethod
    def from_str(cls, indata: str) -> "BCSAddress":
        """."""
        return cls(hexstring_to_list(indata))


class BCSDigest(canoser.Struct):
    """BCSDigest represents a transaction or object base58 value.

    :ivar _fields: Contains the Digest BCS descriptor
    :ivar type _fields: list[int]
    """

    _fields = [("Digest", canoser.ArrayT(canoser.Uint8, _BCS_DIGEST_LENGTH))]

    @classmethod
    def from_str(cls, indata: str) -> "BCSDigest":
        """."""
        return cls(b58str_to_list(indata))


class BCSObjectReference(canoser.Struct):
    """BCSObjectReference represents an objects reference data.

    :ivar _fields: Contains the ObjectID,SequenceNumber and Digest BCS descriptor
    :ivar type _fields: list[int]
    """

    _fields = [
        ("ObjectID", BCSAddress),
        ("SequenceNumber", canoser.Uint64),
        ("ObjectDigest", BCSDigest),
    ]

    @classmethod
    def from_generic_ref(cls, indata: GenericRef) -> "BCSObjectReference":
        """."""
        return cls(BCSAddress.from_str(indata.object_id), indata.version, BCSDigest.from_str(indata.digest))


class BCSSharedObjectReference(canoser.Struct):
    """."""

    _fields = [
        ("ObjectID", BCSAddress),  # canoser.ArrayT(canoser.Uint8, _BCS_ADDRESS_LENGTH)),
        ("SequenceNumber", canoser.Uint64),
        ("Mutable", bool),
    ]

    @classmethod
    def from_generic_ref(cls, indata: GenericRef) -> "BCSSharedObjectReference":
        """."""
        return cls(BCSAddress.from_str(indata.object_id), indata.version, BCSDigest.from_str(indata.digest))


class BCSOptionalU64(canoser.RustOptional):
    """BCSOptionalU64 Optional assignment of unsigned 64 bit int.

    :ivar _type: Identifies this object as unsigned 64 bit int.
    :ivar type _type: canoser.Uint64
    """

    _type = canoser.Uint64


class Uint256(canoser.int_type.IntType):
    """Uint256 represents a 256 bit ulong as hack as canoser doesn't support."""

    byte_lens = 32
    max_value = 115792089237316195423570985008687907853269984665640564039457584007913129639935
    min_value = 0
    signed = False

    @classmethod
    def encode(cls, value):
        """."""
        return value.to_bytes(32, byteorder="little", signed=False)


class TypeTag(canoser.RustEnum):
    """TypeTag enum for move call type_arguments."""

    _enums = [
        ("Bool", bool),
        ("U8", canoser.Uint8),
        ("U64", canoser.Uint64),
        ("U128", canoser.Uint128),
        ("Address", BCSAddress),
        ("Signer", None),
        ("Vector", None),  # Injected below StructTag
        ("Struct", None),  # Injected below StructTag
        ("U16", canoser.Uint16),
        ("U32", canoser.Uint32),
        ("U256", Uint256),
    ]

    @classmethod
    def update_value_at(cls, index: int, value: Any):
        """."""
        cls._enums[index] = (cls._enums[index][0], value)


class StructTag(canoser.Struct):
    """StructTag."""

    _fields = [("address", BCSAddress), ("module", str), ("name", str), ("type_parameters", [TypeTag])]


# Overcome forward reference at init time with these injections
TypeTag.update_value_at(6, [TypeTag])
TypeTag.update_value_at(7, StructTag)


class ObjectArg(canoser.RustEnum):
    """ObjectArg."""

    _enums = [("ImmOrOwnedObject", BCSObjectReference), ("SharedObject", BCSSharedObjectReference)]


class CallArg(canoser.RustEnum):
    """CallArg."""

    _enums = [("Pure", [canoser.Uint8]), ("Object", ObjectArg), ("ObjVec", [ObjectArg])]


class BCSMoveCall(canoser.Struct):
    """BCSMoveCall represents a sui_moveCall structure."""

    _fields = [
        ("package", BCSAddress),
        ("module", str),
        ("function", str),
        ("type_arguments", [TypeTag]),
        ("arguments", [CallArg]),
    ]


class BCSPay(canoser.Struct):
    """BCSPay represents a sui_pay structure."""

    _fields = [
        ("coins", [BCSObjectReference]),
        ("recipients", [BCSAddress]),
        ("amounts", [canoser.Uint64]),
    ]


class BCSPaySui(canoser.Struct):
    """BCSPaySui represents a sui_paySui structure.

    **Not Supported in sui_devInspectTransaction yet.**
    """

    _fields = [
        ("coins", [BCSObjectReference]),
        ("recipients", [BCSAddress]),
        ("amounts", [canoser.Uint64]),
    ]


class BCSPayAllSui(canoser.Struct):
    """BCSPayAllSui represents a sui_payAllSui structure.

    **Not Supported in sui_devInspectTransaction yet.**
    """

    _fields = [
        ("coins", [BCSObjectReference]),
        ("recipient", BCSAddress),
    ]


class BCSTransferObject(canoser.Struct):
    """BCSTransferObject represents a sui_transferObjecrt structure."""

    _fields = [
        ("recipient", BCSAddress),
        ("object_ref", BCSObjectReference),
    ]


class BCSTransferSui(canoser.Struct):
    """BCSTransferSui represents a sui_transferSui structure."""

    _fields = [
        ("recipient", BCSAddress),
        ("amount", BCSOptionalU64),
    ]


class BCSPublish(canoser.Struct):
    """BCSPublish represents a sui_publish structure.

    **Not Supported in sui_devInspectTransaction yet.**
    """

    _fields = [("modules", canoser.ArrayT(canoser.ArrayT(canoser.Uint8)))]


class BCSSingleTransaction(canoser.RustEnum):
    """BCSSingleTransaction is enumeration of different single (not batch) transactions."""

    _enums = [
        ("TransferObject", BCSTransferObject),  # Works
        ("Publish", BCSPublish),  # Not Works
        ("Call", BCSMoveCall),  # Works
        ("TransferSui", BCSTransferSui),  # Works
        ("Pay", BCSPay),  # Works
        ("PaySui", BCSPaySui),  # Not work
        ("PayAllSui", BCSPayAllSui),  # Not work
        ("ChangeEpoch", None),  # Not implemented
        ("Genesis", None),  # Not implemented
    ]

    @classmethod
    def variant_for_index(cls, index: int) -> Union[tuple[str, canoser.RustEnum], ValueError]:
        """."""
        if index > len(cls._enums):
            raise ValueError(f"{cls.__name__} has only {len(cls._enums)} and index requested is greater {index}")
        return cls._enums[index]


class BCSBatchTransaction(canoser.Struct):
    """BCSBatchTransaction represents a sui_batchTransaction structure."""

    _fields = [("Singles", [BCSSingleTransaction])]


class BCSTransactionKind(canoser.RustEnum):
    """BCSTransactionKind is enumeration of different transaction types."""

    _enums = [
        ("Single", BCSSingleTransaction),
        ("Batch", BCSBatchTransaction),  # Not implemented
    ]

    @classmethod
    def variant_for_index(cls, index: int) -> Union[tuple[str, canoser.RustEnum], ValueError]:
        """variant_for_index returns the name and BCS type at enum index.

        :param index: The index of which TransactionKind enum varient to return
        :type index: int
        :raises ValueError: Out of range index
        :return: The variant name and value at index
        :rtype: Union[tuple[str, canoser.RustEnum], ValueError]
        """
        if index > len(cls._enums):
            raise ValueError(f"{cls.__name__} has only {len(cls._enums)} and index requested is greater {index}")
        return cls._enums[index]


def txkind_from_txbytes():
    """."""


def bcs_from_rpcresult(no_sign_result: SuiRpcResult) -> Union[tuple[str, canoser.Struct], Exception]:
    """bcs_from_rpcresult converts the transaction bytes from an unsigned transaction result into BCS.

    :param no_sign_result: The result from calling (not signing) transaction
    :type no_sign_result: SuiRpcResult
    :raises NotImplementedError: If not implemented by pysui yet
    :raises AttributeError: Unrecognized TransactionKind
    :raises ValueError: If no_sign_result success if False
    :return: The BCS decoded transaction kind (i.e. Pay, TransferSui, MoveCall, etc.)
    :rtype: Union[tuple[str, canoser.Struct], Exception]
    """
    if no_sign_result.is_ok():
        _, txbytes = no_sign_result.result_data
        tx_kind = base64.b64decode(txbytes.value)
        # The first byte is index of TransactionKind variant (enum)
        tkind_name, tkind_class = BCSTransactionKind.variant_for_index(tx_kind[_TKIND_INDEX])
        match tkind_name:
            case "Single":
                # The second byte is index into concrete transaction type enum
                tk_name, tx_type_class = tkind_class.variant_for_index(tx_kind[_SUB_TKIND_INDEX])
                if tx_type_class:
                    # print(list(tx_kind))
                    sheded = tx_kind[:-97]
                    sheded = sheded[2:]
                    return tk_name, tx_type_class.deserialize(sheded)
                return tk_name, tx_type_class
            case "Batch":
                sheded = tx_kind[:-97]
                sheded = sheded[1:]
                bdser = BCSBatchTransaction.deserialize(sheded)
                return "Batch", bdser

            case _:
                raise AttributeError(f"{tkind_name} is unknown TransactionKind")
    else:
        raise ValueError(f"RPC result is invalid {no_sign_result.result_string}")


def _bcs_reference_for_oid(client: SyncClient, object_id: ObjectID) -> Union[BCSObjectReference, Exception]:
    result = client.get_object(object_id)
    if result.is_ok():
        return BCSObjectReference.from_generic_ref(result.result_data.reference)
    raise ValueError(f"{result.result_string} fetching object {object_id}")


def bcs_from_builder(client: SyncClient, builder: _MoveCallTransactionBuilder) -> Union[BCSTransactionKind, Exception]:
    """."""
    bname = builder.__class__.__name__
    tx_kind = "Single"

    if isinstance(builder, _MoveCallTransactionBuilder):
        match bname:
            case "TransferObject":
                recipient = BCSAddress.from_sui_address(builder.recipient)
                reference = _bcs_reference_for_oid(client, builder.object_id)
                payload = BCSSingleTransaction(bname, BCSTransferObject(recipient, reference))
            case "TransferSui":
                recipient = BCSAddress.from_sui_address(builder.recipient)
                amount = BCSOptionalU64(builder.amount.value)
                payload = BCSSingleTransaction(bname, BCSTransferSui(recipient, amount))
            case "Pay" | "PaySui":
                coins = [_bcs_reference_for_oid(client, x.value) for x in builder.input_coins.coins]
                amounts = [x.value for x in builder.amounts.amounts]
                recipients = [BCSAddress.from_sui_address(x) for x in builder.recipients.recipients]
                if bname == "Pay":
                    payload = BCSSingleTransaction(bname, BCSPay(coins, recipients, amounts))
                else:
                    payload = BCSSingleTransaction(bname, BCSPaySui(coins, recipients, amounts))
            case "PayAllSui":
                coins = [_bcs_reference_for_oid(client, x.value) for x in builder.input_coins.coins]
                recipient = BCSAddress.from_sui_address(builder.recipient)
                payload = BCSSingleTransaction(bname, BCSPayAllSui(coins, recipient))
            case "Publish":
                modules = [b64str_to_list(x.value) for x in builder.compiled_modules.compiled_modules]
                payload = BCSSingleTransaction(bname, BCSPublish(modules))
            case "MoveCall":
                # package = BCSAddress.from_sui_address(builder.package_object_id)
                # module = builder.module.value
                # function = builder.function.value
                # type_args = []
                # arguments = builder.arguments
                # payload = BCSSingleTransaction(bname, BCSMoveCall(package, module, function, type_args, arguments))
                raise NotImplementedError("MoveCall not implemented yet")
            case "BatchTransaction":
                # tx_kind = "Batch"
                # txs = [builder.transaction_params]
                raise NotImplementedError("BatchTransaction not implemented yet")
            case _:
                raise TypeError(f"conversion from type {bname} builder not supported")
    return BCSTransactionKind(tx_kind, payload)


def bcs_base64_from_builder(client: SyncClient, builder: _MoveCallTransactionBuilder) -> Union[str, Exception]:
    """bcs_base64_from_builder converts a builder to BCS serialized base64 string.

    :param client: The sui synch client
    :type client: pysui.sui.sui_clients.sync_client.SuiClient
    :param builder: The constructed builder
    :type builder: _MoveCallTransactionBuilder
    :return: If successful, a base64 string otherwise Exception
    :rtype: Union[str, Exception]
    """
    return base64.b64encode(bcs_from_builder(client, builder).serialize()).decode()


if __name__ == "__main__":
    pass
