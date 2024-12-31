"""
Embedded domain-specific library for implicitly and explicitly encoding
functions as matrices that operate on domains of one-hot vectors.
"""
from __future__ import annotations
from typing import Any, Union, Iterable, Callable
import doctest
import inspect
import functools

def _dot(xs: Iterable, ys: Iterable) -> Any:
    """
    Return the dot product of two iterables.

    >>> _dot([1, 2, 3], [4, 5, 6])
    32
    """
    return sum(x * y for (x, y) in zip(xs, ys))

class onehot:
    """
    Data structure for an individual one-hot vector.

    >>> v = onehot(7, 16)
    >>> int(v)
    7
    >>> list(v)
    [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    """
    def __init__(self: onehot, index: int, size: int):
        self.index = index
        self.size = size

    def __int__(self: onehot):
        """
        Return the index of the sole `1` entry in the one-hot vector
        that this instance represents.

        >>> int(onehot(3, 4))
        3
        """
        return self.index

    def __iter__(self: onehot) -> Iterable[int]:
        """
        Yield the individual entries of the one-hot vector that this instance
        represents.

        >>> list(onehot(3, 4))
        [0, 0, 0, 1]
        """
        for i in range(self.size):
            yield 1 if i == self.index else 0

class domain:
    """
    Data structure for a domain of values that can be represented as a set of
    one-hot vectors.

    >>> a = domain(['a', 'b', 'c'])
    >>> len(a)
    3
    """
    def __init__(self: domain, iterable: Iterable):
        self.components = [iterable]
        self.inverses = [{x: i for (i, x) in enumerate(iterable)}]

    def __mul__(self: domain, other: domain) -> domain:
        """
        Combine two domains using the Cartesian product operation. This
        operation is associative.

        >>> a = domain(['a', 'b'])
        >>> b = domain(range(2))
        >>> c = a * b
        >>> list(c)
        [('a', 0), ('a', 1), ('b', 0), ('b', 1)]
        """
        d = domain([])
        d.components = self.components + other.components
        d.inverses = self.inverses + other.inverses
        return d

    def __call__(self: domain, value: Any) -> onehot:
        """
        Retrieve the one-hot vector that represents the specified value in this
        domain.

        >>> a = domain(['a', 'b', 'c'])
        >>> b = domain(range(4))
        >>> c = a * b
        >>> list(c(('b', 2)))
        [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]
        """
        if len(self.components) == 1:
            return self.inverses[0][value]

        index = 0
        factor = 1
        for (x, inv) in reversed(list(zip(value, self.inverses))):
            index += factor * inv[x]
            factor *= len(inv)

        return onehot(index, len(self))

    def __getitem__(self: domain, index: Union[int, onehot]) -> Any:
        """
        Retrieve a value in the domain using its index (*i.e.*, the index of
        the sole `1` entry in the one-hot vector that represents the value).

        >>> a = domain(['a', 'b', 'c'])
        >>> b = domain(range(4))
        >>> c = a * b
        >>> c[6]
        ('b', 2)
        """
        if not isinstance(index, int):
            index = list(index).index(1)

        components = []
        for i in range(len(self.components) - 1, -1, -1):
            length = len(self.components[i])
            components.append(self.components[i][index % length])
            index //= length

        components = tuple(reversed(components))
        return components[0] if len(self.components) == 1 else components

    def __iter__(self: domain) -> Iterable:
        """
        Yield the individual elements of this domain.

        >>> list(domain(['a', 'b', 'c']))
        ['a', 'b', 'c']
        """
        for i in range(len(self)):
            yield self[i]

    def __len__(self: domain) -> int:
        """
        Return the size of this domain.

        >>> a = domain(['a', 'b', 'c'])
        >>> b = domain(range(4))
        >>> c = a * b
        >>> len(c)
        12
        """
        size = 1
        for component in self.components:
            size *= len(component)

        return size

class matrix:
    """
    Data structure for representing a function as a matrix that can be applied
    to one-hot vectors.

    >>> uint2 = domain(range(4))
    >>> enum3 = domain(['less', 'same', 'more'])
    >>> def compare(x: uint2, y: uint2) -> enum3:
    ...     if x < y:
    ...         return 'less'
    ...     elif x > y:
    ...         return 'more'
    ...     else:
    ...         return 'same'
    >>> m = matrix(compare, uint2 * uint2, enum3)
    >>> v = (uint2 * uint2)((3, 2))
    >>> tuple(m @ v)
    (0, 0, 1)
    >>> enum3[tuple(m @ v)]
    'more'

    If the domain and codomain are not explicitly provided to the constructor,
    the constructor attemps to find them in the context.

    >>> def identity(x: 'domain(range(4))') -> 'domain(range(4))':
    ...     return x
    >>> isinstance(matrix(identity), matrix)
    True
    """
    def __init__(
            self: matrix,
            function: Callable,
            domain: domain = None, # pylint: disable=redefined-outer-name
            codomain: domain = None
        ):
        self.function = function

        if domain is None:
            signature = inspect.signature(self.function)
            parameters = signature.parameters
            domains = []
            for parameter in parameters:
                # pylint: disable=eval-used
                domains.append(eval(parameters[parameter].annotation))
            domain = functools.reduce((lambda a, b: a * b), domains)
        self.domain = domain

        if codomain is None:
            # pylint: disable=eval-used
            codomain = eval(signature.return_annotation)
        self.codomain = codomain

    def __matmul__(self: matrix, other: onehot) -> onehot:
        """
        Apply the function represented by this instance to the supplied one-hot
        vector.

        >>> uint2 = domain(range(4))
        >>> def maximum(x: uint2, y: uint2) -> uint2:
        ...     return max(x, y)
        >>> m = matrix(maximum, uint2 * uint2, uint2)
        >>> v = (uint2 * uint2)((3, 2))
        >>> tuple(m @ v)
        (0, 0, 0, 1)
        """
        result = [0 for  _ in range(len(self.codomain))]

        for i in range(len(self.domain)): # pylint: disable=consider-using-enumerate
            index = self.codomain(self.function(*self.domain[i]))
            result[index] += _dot(list(onehot(i, len(self.domain))), other)

        yield from result

    def __iter__(self: matrix) -> Iterable:
        """
        Yield the individual rows of the matrix represented by this instance.

        >>> uint2 = domain(range(4))
        >>> def maximum(x: uint2, y: uint2) -> uint2:
        ...     return max(x, y)
        >>> m = matrix(maximum, uint2 * uint2, uint2)
        >>> for row in m:
        ...     print(row)
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        [0, 1, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        [0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0]
        [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1]
        """
        rows = [
            [0 for _ in range(len(self.domain))]
            for  _ in range(len(self.codomain))
        ]

        for i in range(len(self.domain)): # pylint: disable=consider-using-enumerate
            index = self.codomain(self.function(*self.domain[i]))
            rows[index][i] += 1

        yield from rows

if __name__ == '__main__':
    doctest.testmod() # pragma: no cover
