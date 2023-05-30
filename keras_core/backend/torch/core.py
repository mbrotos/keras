import contextlib

import torch

from keras_core.backend.common import KerasVariable
from keras_core.backend.common import standardize_dtype

DYNAMIC_SHAPES_OK = True


TORCH_DTYPES = {
    "float16": torch.float16,
    "float32": torch.float32,
    "float64": torch.float64,
    "uint8": torch.uint8,
    "uint32": torch.int64,  # TODO: Torch doesn't have `uint32` dtype.
    "int8": torch.int8,
    "int16": torch.int16,
    "int32": torch.int32,
    "int64": torch.int64,
    "bfloat16": torch.bfloat16,
    "bool": torch.bool,
}


def to_torch_dtype(dtype):
    if isinstance(dtype, torch.dtype):
        return dtype
    dtype = standardize_dtype(dtype)
    dtype = TORCH_DTYPES.get(dtype, None)
    if dtype is None:
        raise ValueError(f"Unsupported dtype for PyTorch: {dtype}")
    return dtype


class Variable(KerasVariable):
    def _initialize(self, value):
        self._value = convert_to_tensor(value, dtype=self._dtype)

    def _direct_assign(self, value):
        self._value = value

    def _convert_to_tensor(self, value, dtype=None):
        return convert_to_tensor(value, dtype=dtype)

    # Overload native accessor.
    def __torch_function__(self, func, types, args=(), kwargs=None):
        return func(self.value, *args, **kwargs)


def convert_to_tensor(x, dtype=None):
    # TODO: Need to address device placement arg of `as_tensor`
    dtype = to_torch_dtype(dtype or getattr(x, "dtype", None))
    if isinstance(x, Variable):
        if dtype and dtype != x.dtype:
            return x.value.to(dtype)
        return x.value
    return torch.as_tensor(x, dtype=dtype)


def is_tensor(x):
    return torch.is_tensor(x)


def shape(x):
    return x.shape


def cast(x, dtype):
    dtype = to_torch_dtype(dtype)
    return x.to(dtype)


def name_scope(name):
    return contextlib.nullcontext()


# Shape / dtype inference util
def compute_output_spec(fn, *args, **kwargs):
    raise NotImplementedError(
        "`compute_output_spec` not implemented for PyTorch backend"
    )


def cond(pred, true_fn, false_fn):
    if pred:
        return true_fn()
    return false_fn()


def vectorized_map(function, elements):
    return torch.vmap(function)(elements)


def scatter(indices, values, shape):
    indices = convert_to_tensor(indices)
    values = convert_to_tensor(values)
    zeros = torch.zeros(shape, dtype=values.dtype)

    index_length = indices.shape[-1]
    value_shape = shape[index_length:]
    indices = torch.reshape(indices, [-1, index_length])
    values = torch.reshape(values, [-1] + list(value_shape))

    for i in range(indices.shape[0]):
        index = indices[i]
        zeros[tuple(index)] += values[i]
    return zeros


def scatter_update(inputs, indices, updates):
    inputs = convert_to_tensor(inputs)
    indices = convert_to_tensor(indices, dtype="int64")
    updates = convert_to_tensor(updates)
    indices = torch.transpose(indices, 0, 1)

    inputs[tuple(indices)] = updates
    return inputs


def block_update(inputs, start_indices, updates):
    inputs = convert_to_tensor(inputs)
    start_indices = convert_to_tensor(start_indices, dtype="int64")
    updates = convert_to_tensor(updates)

    update_shape = updates.shape
    slices = [
        slice(start_index, start_index + update_length)
        for start_index, update_length in zip(start_indices, update_shape)
    ]
    inputs[slices] = updates
    return inputs