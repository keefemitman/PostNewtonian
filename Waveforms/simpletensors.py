from __future__ import division
# import sympy
from sympy import simplify, Function, latex, prod, Symbol, flatten
from sympy import Rational as frac

def DifferentiateString(s, param='t'):
    "Add latex to string indicating differentiation by time."
    if(s.startswith(r'\partial_{0}^{{'.format(param))):
        from re import sub
        def increment_match(match):
            return r'\partial_{0}^{{{1}}}{2}'.format(param, int(match.group(1))+1, match.group(2))
        return sub(r'\\partial_.*?\^\{(.*)\}(.*)', increment_match, s)
    elif(s.startswith(r'\partial_{0}'.format(param))):
        return r'\partial_{0}^{{2}}'.format(param) + s[10:]
    else:
        return r'\partial_{0} '.format(param) + s

def DelimitString(S, latex=True):
    "Surround string by parentheses, brackets, or braces as appropriate"
    if(latex):
        left, right = [r'\left', r'\right']
        DelimiterOpeners, DelimiterClosers = [['(','[','\{'], [')',']','\}']]
    else:
        left, right = ['', '']
        DelimiterOpeners, DelimiterClosers = ['([{', ')]}']
    def FindFirst(S, D):
        for s in S:
            for d in D:
                if(s==d):
                    return d
    FirstDelim = FindFirst(S, DelimiterOpeners)
    if(not FirstDelim):
        return left+'('+S+right+')'
    NewDelimiterIndex = (DelimiterOpeners.index(FindFirst(S, DelimiterOpeners))+1) % len(DelimiterOpeners)
    return r'{0}{1} {2} {3}{4}'.format(left, DelimiterOpeners[NewDelimiterIndex],
                                       S, right, DelimiterClosers[NewDelimiterIndex])


####################################
### First, a few vector thingies ###
####################################
class _VectorFunction(Function):
    """\
    This is just a base class for deriving other vectors from.

    You probably won't need to use this class directly; it is just the
    base class for the class created in _VectorFunctionFactory below.

    This used to be more important because there were other subclasses
    of this, but now it's mostly just for convenient separation of a
    few methods, to clarify what's going on in the factory.

    """
    components = None
    @property
    def name(self):
        return self.__class__.__name__
    def __or__(self,other):
        """
        In keeping with the notation of various other packages
        (most notably sympy.galgebra), contraction is denoted
        by the bitwise `or` operator.  So the contraction of
        vectors `v` and `w` is just `v|w`.  This notation will
        be used in the tensor classes also.
        """
        return sum( s*o for s,o in zip(self, other) )
    def __iter__(self):
        for c in self.__class__.components: yield c
    def diff(self, *args, **kwargs):
        return self._eval_derivative(*args, **kwargs)
    def __mul__(self, other):
        if(hasattr(other, '_is_tensor_product') or hasattr(other, '_is_tensor')):
            return NotImplemented
    def __rmul__(self, other):
        if(hasattr(other, '_is_tensor_product') or hasattr(other, '_is_tensor')):
            return NotImplemented


def VectorFunction(Name, ComponentFunctions, DerivativeFunction=None):
    """Create a new vector function

    This function creates a class that is a subclass of
    `_VectorFunction`, which is itself a subclass of
    `sympy.Function`.  Thus, the resulting quantity should be
    differentiable.  The class is created, and a class variable set to
    store the input components.  Then, if no derivative has been
    defined, one is defined for you, assuming that each component
    should be differentiated.  Alternatively, you can pass in a lambda
    function as the final argument.  It should take as inputs `self,
    *args, **kwargs`, and evaluate the value of the derivative from
    that information.  Finally, the class is renamed to carry the
    input name, so that sympy output looks nice, etc.
    """
    class Vector(_VectorFunction):
        components = ComponentFunctions
    if(DerivativeFunction):
        Vector._eval_derivative = DerivativeFunction
    else:
        Vector._eval_derivative = lambda self, *args, **kwargs: \
                                  VectorFunction(DifferentiateString(Name, self.args[0]),
                                                 [c._eval_derivative(args[0])
                                                  for c in ComponentFunctions])(self.args[0])
    Vector.__name__ = Name
    return Vector

def VectorConstant(Name, Components):
    return VectorFunction(Name, Components, lambda self, *args, **kwargs: 0)



################################
### Now, the tensor products ###
################################
class _TensorProductFunction(Function):
    vectors = None
    coefficient = None
    symmetric = False

    @property
    def LaTeXProductString(self):
        if(self.symmetric):
            return r' \otimes_{\mathrm{s}} '
        else:
            return r' \otimes '

    @property
    def _is_tensor_product(self):
         return True

    # @property
    # def name(self):
    #     return self.__class__.__name__

    @property
    def rank(self):
        return len(self.vectors)

    def __iter__(self):
        for v in self.vectors: yield v

    def has_same_basis_element(self, B):
        if(self.symmetric):
            from collections import Counter
            return Counter(self.vectors) == Counter(B.vectors)
        return self.vectors == B.vectors

    def ordered_as(self, index_set):
        for i in index_set:
            yield self.vectors[i]

    def __or__(self,B):
        if(B.rank != self.rank):
            raise ValueError("Cannot contract rank-{0} tensor with rank-{1} tensor.".format(self.rank, B.rank))
        if(isinstance(B, _TensorProductFunction)):
            if(self.symmetric):
                from itertools import permutations
                # It suffices to just iterate over rearrangements of `self`.
                coefficient = simplify(self.coefficient*B.coefficient*frac(1,factorial(self.rank)))
                if(coefficient==0): return 0
                return simplify( coefficient * sum([prod([v|w for v,w in zip(self.ordered_as(index_set), B)])
                                                    for index_set in permutations(range(self.rank))]) )
            return (self.coefficient*B.coefficient)*prod([v|w for v,w in zip(self, B)])
        else:
            try:
                return sum( [(self|t_p) for t_p in B] )
            except AttributeError:
                raise ValueError("Don't know how to contract _TensorProductFunction with '{0}'".format(type(B)))

    def trace(self, j, k):
        coefficient = simplify(self.coefficient * (self.vectors[j]|self.vectors[k]))
        if(self.rank==2):
            return coefficient
        if(coefficient==0): return 0
        if(self.symmetric):
            if(self.rank==2):
                return simplify( self.coefficient * (self.vectors[0]|self.vectors[1]) )
            from itertools import permutations
            T = 0
            for j,k in permutations(range(self.rank), 2):
                coefficient = simplify( self.coefficient * (self.vectors[j]|self.vectors[k]) )
                if(coefficient==0):
                    continue
                T += TensorProduct(list(v for i,v in enumerate(self.vectors) if (i!=j and i!=k)),
                                   coefficient = coefficient*frac(1,factorial(self.rank)),
                                   symmetric=True)
            return T.compress()
        return TensorProduct(list(v for i,v in enumerate(self) if (i!=j and i!=k)),
                             coefficient=coefficient, symmetric=False)

    def __mul__(self, B):
        """
        Return the scalar or tensor product
        """
        #print('_TensorProductFunction.__mul__')
        #print(type(B), type(self))
        if(simplify(B)==0): return 0
        if(hasattr(B, '_is_tensor') and B._is_tensor):
            # Fall back to Tensor.__rmul__ by doing this:
            return NotImplemented
        if(isinstance(B, _TensorProductFunction)):
            # Do tensor product
            #print('_TensorProductFunction.__mul__ return 1')
            return TensorProduct(self.vectors + B.vectors,
                                 coefficient=simplify( self.coefficient * B.coefficient ),
                                 symmetric = self.symmetric)
        elif(isinstance(B, _VectorFunction)):
            #print('_TensorProductFunction.__mul__ return 2')
            return TensorProduct(self.vectors + [B,],
                                 coefficient=self.coefficient,
                                 symmetric = self.symmetric)
        else:
            # Otherwise, try scalar multiplication
            #print('_TensorProductFunction.__mul__ return 3')
            return TensorProduct(self.vectors,
                                 coefficient=self.coefficient*B,
                                 symmetric = self.symmetric)

    def __rmul__(self, B):
        """
        Return the scalar or tensor product
        """
        #print('_TensorProductFunction.__rmul__')
        #print(type(B), type(self))
        if(simplify(B)==0): return 0
        if(hasattr(B, '_is_tensor') and B._is_tensor):
            # Fall back to Tensor.__rmul__ by doing this:
            return NotImplemented
        if(isinstance(B, _TensorProductFunction)):
            # Do tensor product
            #print('_TensorProductFunction.__rmul__ return 1')
            return TensorProduct(B.vectors+self.vectors,
                                 coefficient=simplify( B.coefficient * self.coefficient ),
                                 symmetric = self.symmetric)
        elif(isinstance(B, _VectorFunction)):
            #print('_TensorProductFunction.__rmul__ return 2')
            return TensorProduct([B,] + self.vectors,
                                 coefficient=self.coefficient,
                                 symmetric = self.symmetric)
        else:
            # Otherwise, try scalar multiplication
            #print('_TensorProductFunction.__rmul__ return 3')
            return TensorProduct(self.vectors,
                                 coefficient=B*self.coefficient,
                                 symmetric = self.symmetric)

    # These two will be defined below, once we have defined Tensor
    # objects:
    # _TensorProductFunction.__add__ = lambda self, T: Tensor(self)+T
    # _TensorProductFunction.__radd__ = _TensorProductFunction.__add__

    def __str__(self):
        if(self.coefficient==1):
            return DelimitString('*'.join([str(v) for v in self]), latex=False)
        return DelimitString( DelimitString(str(self.coefficient))
                              + '*' + '*'.join([str(v) for v in self]) )

    def __repr__(self):
        if(self.coefficient==1):
            return DelimitString('*'.join([repr(v) for v in self]), latex=False)
        return DelimitString( DelimitString(str(self.coefficient))
                              + '*' + '*'.join([repr(v) for v in self]) )

    def _latex_str_(self):
        if(self.coefficient==1):
            return DelimitString( self.LaTeXProductString.join([latex(v) for v in self]) )
        return DelimitString( DelimitString(latex(self.coefficient)) + '\, '
                              + self.LaTeXProductString.join([latex(v) for v in self]) )

    def _latex(self, printer):
        #printer._settings['mode'] = 'align*'
        return r'&\left\{{\sum_i^{{\infty}}\left({0}\right)\right. \\ &\left.\quad b\right\}}'.format(','.join([ str(printer._print(arg)) for arg in self.args ]))

    def _latex(self, printer):
        "Sympy looks for this when latex printing is on"
        printer._settings['mode'] = 'equation*'
        return self._latex_str_()

    def _repr_latex_(self):
        return '$'+ self._latex_str_() + '$'


def TensorProduct(*input_vectors, **kwargs):
    if(len(input_vectors)==1 and isinstance(input_vectors[0], _TensorProductFunction)) :
        class TensorProductFunction(_TensorProductFunction):
            vectors = input_vectors[0].vectors
            coefficient = input_vectors[0].coefficient
            symmetric = input_vectors[0].symmetric
    else:
        if(len(input_vectors)==1 and isinstance(input_vectors[0], list)):
            input_vectors = input_vectors[0]
        class TensorProductFunction(_TensorProductFunction):
            vectors = list(input_vectors)
            coefficient = kwargs.get('coefficient', 1)
            symmetric = kwargs.get('symmetric', False)
    # TensorProductFunction.__name__ = TensorProductFunction(Symbol('t'))._latex_str_()
    return TensorProductFunction( *tuple( set( flatten( [v.args for v in TensorProductFunction.vectors] ) ) ) )

##############################
### And tensors themselves ###
##############################
class _TensorFunction(Function):
    """
    This is just a base class for deriving other tensors from.

    You probably won't need to use this class directly; it is just the
    base class for the class created in _TensorFunctionFactory below.

    Technically, this could all be in the factory, but I think it's
    nice to separate the more universal elements of the tensor from
    its factory.
    """

    tensor_products = None

    @property
    def _is_tensor(self):
        """Since this is a property, it can be called without parentheses.
        But I want to make sure it applies to the instance, not the
        class, so it shouldn't just be a variable."""
        return True

    # @property
    # def name(self):
    #     return self.__class__.__name__

    @property
    def rank(self):
        if(len(self.tensor_products)==0):
            return 0
        return self.tensor_products[0].rank

    def __iter__(self):
        if self.tensor_products:
            for t_p in self.tensor_products: yield t_p
        else:
            raise StopIteration()

    def compress(self):
        #display(self)
        removed_elements = []
        for i in range(len(self.tensor_products)):
            if(i in removed_elements):
                continue
            for j in range(i+1,len(self.tensor_products)):
                if(j in removed_elements):
                    continue
                if self.tensor_products[i].has_same_basis_element(self.tensor_products[j]):
                    #print("Removing {0} because {1} is already here".format(j,i))
                    self.tensor_products[i].coefficient = \
                        simplify( self.tensor_products[i].coefficient + self.tensor_products[j].coefficient )
                    removed_elements.append(j)
            if removed_elements:
                if(self.tensor_products[i].coefficient==0):
                    removed_elements += [i]
                #print("Removing {0} because {1} is already here".format(removed_elements,i))
        self.tensor_products = list(t_p for i,t_p in enumerate(self) if i not in removed_elements)
        if not self.tensor_products:
            return 0
        return self

    def __add__(self, T):
        if(T==0):
            return self
        if(self.rank==0):
            return T
        if(T.rank==0):
            return self
        if(T.rank!=self.rank):
            raise ValueError("Cannot add rank-{0} tensor to rank-{1} tensor.".format(T.rank, self.rank))
        if(isinstance(T, _TensorFunction)) :
            return Tensor(self.tensor_products + T.tensor_products)
        elif(isinstance(T, _TensorProductFunction)) :
            return Tensor(self.tensor_products + [T,])

    def __radd__(self, T):
        """Addition is commutative, but python might get here when T is a
        TensorProduct or something"""
        return self+T

    def __or__(self, B):
        if(B.rank != self.rank):
            raise ValueError("Cannot contract rank-{0} tensor with rank-{1} tensor.".format(self.rank, B.rank))
        if(isinstance(B, _TensorFunction)) :
            return sum([T1|T2 for T1 in self for T2 in B])
        elif(isinstance(B, _TensorProductFunction)) :
            return sum([T1|B  for T1 in self])

    def trace(self, j=0, k=1):
        t = sum([T.trace(j,k) for T in self])
        try:
            #print("Trying to compress the Tensor trace")
            return t.compress()
        except:
            #print("Failed to compress the Tensor trace")
            return t

    def __mul__(self, B):
        #print('Tensor.__mul__')
        if(isinstance(B, _TensorFunction)):
            #print('TensorFunction.__mul__ return 1')
            return Tensor(list(t_pA*t_pB for t_pA in self for t_pB in B))
        else:
            #print('TensorFunction.__mul__ return 2')
            return Tensor(list(t_p*B for t_p in self))

    def __rmul__(self, B):
        #print('TensorFunction.__rmul__')
        if(isinstance(B, _TensorFunction)):
            #print('TensorFunction.__rmul__ return 1')
            return Tensor(list(t_pB*t_pA for t_pA in self for t_pB in B))
        else:
            #print('TensorFunction.__rmul__ return 2')
            return Tensor(list(B*t_p for t_p in self))

    def diff(self, *args, **kwargs):
        return self._eval_derivative(*args, **kwargs)

    def _eval_derivative(self, *args, **kwargs):
        return _TensorFunctionFactory(list(t_p._eval_derivative(*args, **kwargs) for t_p in self))

    def __str__(self):
        return DelimitString( '\n'.join([str(t_p) for t_p in self]), latex=False)

    def __repr__(self):
        return DelimitString( '\n'.join([repr(t_p) for t_p in self]), latex=False)

    def _latex_str_(self):
        return '&' + DelimitString( r' \right. \nonumber \\&\quad \left. + '.join(
            [t_p._latex_str_() for t_p in self]) )

    def _latex(self, printer):
        printer._settings['mode'] = 'align*'
        return self._latex_str_()
            # + DelimitString( ','.join([ str(printer._print(arg)) for arg in self.args ]) )

    def _repr_latex_(self):
        return r'\begin{align}'+ self._latex_str_() + r'\end{align}'


def Tensor(*TensorProducts):
    """Create a new tensor

    This function creates a class that is a subclass of
    `_TensorFunction`, which is itself a subclass of `sympy.Function`.
    Thus, the resulting quantity should be differentiable.  The class
    is created, and a class variable set to store the input
    TensorProduct objects, of which this tensor is a sum.  Then, the
    class is renamed to carry the input `Name`, so that sympy output
    looks nice, etc.  Note that `Name` can be an arbitrary string, and
    the class will never be called directly again, so it can really be
    anything.  In particular, it can contain python operators and
    latex commands.  That's okay, since it's just a string.

    """
    if(len(TensorProducts)==1 and isinstance(TensorProducts[0], _TensorFunction)) :
        class TensorFunction(_TensorFunction):
            tensor_products = TensorProducts[0].tensor_products
    elif(len(TensorProducts)==1 and isinstance(TensorProducts[0], _TensorProductFunction)) :
        class TensorFunction(_TensorFunction):
            tensor_products = [TensorProducts[0],]
    else:
        if(len(TensorProducts)==1 and isinstance(TensorProducts[0], list)):
            TensorProducts = TensorProducts[0]
        class TensorFunction(_TensorFunction):
            tensor_products = flatten(list(TensorProducts))
        if(len(TensorFunction.tensor_products)>0):
            rank=TensorFunction.tensor_products[0].rank
            for t_p in TensorFunction.tensor_products:
                if(t_p.rank != rank):
                    raise ValueError("Cannot add rank-{0} tensor to rank-{1} tensors.".format(t_p.rank, rank))
    # tmp = TensorFunction(Symbol('tmp_variable'))
    # print(tmp)
    # TensorFunction.__name__ = tmp._latex_str_()
    return TensorFunction( *tuple( set( flatten( [t_p.args for t_p in TensorFunction.tensor_products] ) ) ) )



# Since the sum of two `TensorProduct`s is a `Tensor`, we
# had to wait until we got here to define these methods:
_TensorProductFunction.__add__ = lambda self, T: Tensor(self)+T
_TensorProductFunction.__radd__ = _TensorProductFunction.__add__



# ##############################################
# ### And finally, symmetric tensor products ###
# ##############################################
# class SymmetricTensorProduct(TensorProduct):

#     """
#     Specialized class for symmetric tensor products

#     **Note:**  If you multiply a SymmetricTensorProduct by
#     any TensorProduct (even if it's not symmetric), the result
#     will be symmetric.  This makes it easy to make STPs, but is
#     not how real tensor products work.

#     This is a subclass of `TensorProduct` with the necessary
#     methods overridden.  Because it is subclassed, and `Tensor`
#     isn't very invasive, we can easily create tensors by adding
#     symmetric tensor products, and the `Tensor` need not even
#     know that it is symmetric.
#     """
#     LaTeXProductString = r' \otimes_{\mathrm{s}} '

#     def __init__(self, *vectors, **kwargs):
#         TensorProduct.__init__(self, *vectors, **kwargs)

#     def has_same_basis_element(self, B):
#         from collections import Counter
#         return Counter(self.vectors) == Counter(B.vectors)

#     def ordered_as(self, index_set):
#         for i in index_set:
#             yield self.vectors[i]

#     def __or__(self,B):
#         if(B.rank != self.rank):
#             raise ValueError("Cannot contract rank-{0} tensor with rank-{1} tensor.".format(self.rank, B.rank))
#         from itertools import permutations
#         from sympy import prod
#         if(isinstance(B, TensorProduct)):
#             # If B is actually a SymmetricTensorProduct, it suffices to just
#             # iterate over rearrangements of `self`.
#             #return self.coefficient*B.coefficient*prod([sum([v[i]*w[i] for i in range(3)]) for v,w in zip(self, B)])
#             coefficient = simplify(self.coefficient*B.coefficient*frac(1,factorial(self.rank)))
#             if(coefficient==0): return 0
#             return simplify( coefficient * sum([prod([v|w for v,w in zip(self.ordered_as(index_set), B)])
#                                                       for index_set in permutations(range(self.rank))]) )
#         elif(isinstance(B, Tensor)):
#             return sum( [self|t_p for t_p in B] )
#         else:
#             raise ValueError("Don't know how to contract SymmetricTensorProduct with '{0}'".format(type(B)))

#     def trace(self, j=0, k=1):
#         """
#         Any input elements are ignored, since we will be symmetrizing anyway
#         """
#         T = Tensor()
#         from itertools import permutations
#         for j,k in permutations(range(self.rank), 2):
#             coefficient = simplify( self.coefficient * (self.vectors[j]|self.vectors[k]) )
#             if(self.rank==2):
#                 return coefficient
#             if(coefficient==0):
#                 continue
#             new = SymmetricTensorProduct()
#             new.vectors = list(v for i,v in enumerate(self.vectors) if (i!=j and i!=k))
#             new.coefficient = coefficient*frac(1,factorial(self.rank))
#             T = T+new
#         return T.compress()
