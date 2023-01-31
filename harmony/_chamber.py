from __future__ import annotations

from abc import abstractmethod
from typing import Callable

import numpy as np
from numpy.random import RandomState


class _Harmonizer(object):
    __cost_dtype = np.float64

    @classmethod
    @property
    def cost_dtype(cls):
        return cls.__cost_dtype

    def __init__(self, obj_func: Callable[[list], float],
                 constraint_func: Callable[[list], bool], **kwargs):
        """
        Base class for optimizers using HarmonySearch Search method.
        """
        # public
        self.hmcr = kwargs['hmcr'] if kwargs.get('hmcr') is not None else 0.9
        self.par = kwargs['par'] if kwargs.get('par') is not None else 0.2
        self.n_iter = kwargs['n_iter'] if kwargs.get('n_iter') is not None else 1000

        # private
        self.__obj_func = obj_func
        self.__constraint_func = constraint_func
        self.__seed = kwargs['seed'] if kwargs.get('seed') is not None else None
        self.__random = RandomState(self.__seed)
        self.__maximize = kwargs['maximize'] if kwargs.get('maximize') is not None else False

    def set(self, hmcr: float, par: float, n_iter: int,
            seed: int, maximize: bool, **kwargs):
        # Preserve previous params and assign new parameters
        pre_params = {
            # public
            'hmcr': self.hmcr,
            'par': self.par,
            'n_iter': self.n_iter,

            # private
            'domain': self.domain[:] if self.domain.n_var > 0 else (),
            'mem_size': self.memory.size,
            'obj_func': self.__obj_func,
            'constraint_func': self.__constraint_func,
            'seed': self.__seed,
            'maximize': self.__maximize
        }
        new_params = {
            #public
            'hmcr': hmcr,
            'par': par,
            'n_iter': n_iter,

            # private
            'domain': kwargs.get('domain'),
            'mem_size': kwargs.get('mem_size'),
            'obj_func': kwargs.get('obj_func'),
            'constraint_func': kwargs.get('constraint_func'),
            'seed': seed,
            'maximize': maximize
        }
        for key in pre_params.keys():
            new_params[key] = pre_params[key] if kwargs.get(key) is None else kwargs[key]

        if kwargs.get('domain') is not None or kwargs.get('mem_size') is not None \
                or kwargs.get('obj_func') is not None or kwargs.get('constraint_func') is not None:
            self.__init__(domain=new_params['domain'], mem_size=new_params['mem_size'],
                          obj_func=new_params['obj_func'], constraint_func=new_params['constraint_func'],
                          hmcr=new_params['hmcr'], par=new_params['par'], n_iter=new_params['n_iter'],
                          seed=new_params['seed'], maximize=new_params['maximize'])
        elif kwargs.get('maximize') is not None and kwargs['maximize'] != self.__maximize:
            self.memory.reverse()

    def search(self):
        """
        Search for minimum cost solutions for given domain.
        """

        ''' For convergence test '''
        min_costs = [self.memory.cost[0]]

        ''' Iteration start '''
        epoch = 0
        while epoch < self.n_iter:  # O(n_iter * hm_size)
            new_members = self._select_members()
            new_cost = self._calc_cost(new_members)

            if self._violate_constraint(new_members) \
                    or not self.maximize and new_cost > self.memory.cost[-1] \
                    or self.maximize and new_cost < self.memory.cost[-1]:
                ''' For convergence test '''
                min_costs.append(self.memory.cost[0])
                continue

            # Insert new member order by cost
            for i_mem in range(self.memory.size):  # O(hm_size)
                if not self.__maximize and self.memory.cost[i_mem] > new_cost \
                        or self.__maximize and self.memory.cost[i_mem] < new_cost:
                    self.memory.insert(i_mem, new_members, new_cost)
                    break

            if _equal(self.memory.cost[0], self.memory.cost[-1]):
                break

            epoch += 1
            ''' For convergence test '''
            min_costs.append(self.memory.cost[0])

        ''' End iteration '''

        solution = self.memory[0]
        return solution, min_costs
    ''' End search '''

    def multiple_search(self):
        """
        Developing...

        :return: Optimal solutions
        """
        solution, min_costs = self.search()

        # Consider multiple solutions
        solutions = solution.reshape(1, self.domain.n_var)

        for i_mem in range(1, self.memory.size):
            if not _equal(self.memory.cost[i_mem], self.memory.cost[0]):
                break

            var_set = self.memory[i_mem]
            is_solution = True
            for i_sol in range(len(solutions)):
                if _similar(var_set, solutions[i_sol]):
                    is_solution = False
                    break

            if is_solution:
                var_set = var_set.reshape(1, self.domain.n_var)
                solutions = np.append(solutions, var_set, axis=0)

        return solutions, min_costs
    ''' End multiple search '''

    ''' helper methods '''
    @abstractmethod
    def _calc_cost(self, members):
        pass

    @abstractmethod
    def _select_members(self):
        pass

    @abstractmethod
    def _violate_constraint(self, members):
        pass

    ''' READ ONLY '''
    @property
    @abstractmethod
    def memory(self):
        pass

    @property
    @abstractmethod
    def domain(self):
        pass

    @property
    def obj_func(self):
        return self.__obj_func

    @property
    def constraint_func(self):
        return self.__constraint_func

    @property
    def _random(self):
        return self.__random

    @property
    def maximize(self):
        return self.__maximize
    ''' End READ ONLY '''

    ''' settable '''
    @property
    def seed(self):
        return self.__seed

    @seed.setter
    def seed(self, seed):
        self.__seed = seed
        self.__random.seed(seed)
    ''' End settable '''

    ''' magic methods '''
    @abstractmethod
    def __str__(self):
        pass
    ''' End magic methods '''

    class _Memory(object):
        def __init__(self, size: int, n_var: int, dtype):
            self.__size = size if size is not None else 0
            self.__memory = np.array([
                [0 for _ in range(n_var)] for _ in range(self.__size)
            ], dtype=dtype) if size * n_var > 0 else None
            self.__cost = np.array([0.0 for _ in range(self.__size)],
                                   dtype=_Harmonizer.cost_dtype)

        def insert(self, mem_idx, new_members, new_cost):
            self.__memory[mem_idx + 1:] = self.__memory[mem_idx:self.__size - 1]
            self.cost[mem_idx + 1:] = self.cost[mem_idx:self.__size - 1]

            self.__memory[mem_idx] = new_members
            self.__cost[mem_idx] = new_cost

        def sort(self, maximize):
            sort_order = self.__cost.argsort()[::-1] if maximize else self.__cost.argsort()
            self.__memory = self.__memory[sort_order]
            self.__cost = self.__cost[sort_order]

        def reverse(self):
            self.__memory = self.__memory[::-1]
            self.__cost = self.__cost[::-1]

        @property
        def cost(self):
            return self.__cost

        @property
        def size(self):
            return self.__size

        def __len__(self):
            return len(self.__memory)

        def __getitem__(self, *args):
            return self.__memory[args[0]]

        def __setitem__(self, *args):
            self.__memory[args[0]] = args[1]

    class _Domain(object):
        def __init__(self, domain):
            self.__domain = domain if domain is not None else ()
            self.__n_var = len(domain) if domain is not None else 0

            if self.__n_var < 1:
                return

            for i_var in range(self.__n_var):
                if isinstance(self.__domain[i_var], np.ndarray):
                    self.__domain[i_var] = np.array(self.__domain[i_var]).flatten()
                elif isinstance(self.__domain[i_var], tuple):
                    self.__domain[i_var] = list(self.__domain[i_var])

                self.__domain[i_var].sort()

            self.__domain = tuple(self.__domain)

        @property
        def n_var(self):
            return self.__n_var

        def __getitem__(self, *args):
            indices = args[0]
            if isinstance(indices, int):
                return self.__domain[indices]
            return self.__domain[indices[0]][indices[1]]


def _similar(this, other):
    return __float_compare(this, other, r_tol=np.finfo(np.float32).eps * 1000)


def _close(this, other):
    return __float_compare(this, other, r_tol=np.finfo(np.float32).eps)


def _equal(this, other):
    return __float_compare(this, other, r_tol=np.finfo(np.float64).eps)


def __float_compare(this, other, r_tol):
    if hasattr(this, '__iter__') and hasattr(other, '__iter__') and len(this) == len(other) \
            or not hasattr(this, '__iter__') and not hasattr(other, '__iter__'):
        return np.allclose(this, other, rtol=r_tol)
    return False
