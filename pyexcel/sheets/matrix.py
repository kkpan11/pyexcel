"""
    pyexcel.sheets.matrix
    ~~~~~~~~~~~~~~~~~~~~~~

    Matrix, a data model that accepts any types, spread sheet style
of lookup.

    :copyright: (c) 2014-2017 by Onni Software Ltd.
    :license: New BSD License, see LICENSE for more details
"""
import copy
from itertools import chain
from functools import partial

import pyexcel._compact as compact
import pyexcel.constants as constants
from pyexcel.sheets.formatters import to_format
from .row import Row
from .column import Column
from . import _shared as utils


def _unique(seq):
    """Return a unique list of the incoming list

    Reference:
    http://stackoverflow.com/questions/480214/
    how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def longest_row_number(array):
    """Find the length of the longest row in the array

    :param list in_array: a list of arrays
    """
    if len(array) > 0:
        # map runs len() against each member of the array
        return max(map(len, array))
    else:
        return 0


def uniform(array):
    """Fill-in empty strings to empty cells to make it MxN

    :param list in_array: a list of arrays
    """
    width = longest_row_number(array)
    if width == 0:
        return 0, array
    else:
        for row in array:
            row_length = len(row)
            for index in range(0, row_length):
                if row[index] is None:
                    row[index] = ""
            if row_length < width:
                row += [""] * (width - row_length)
        return width, array


def transpose(in_array):
    """Rotate clockwise by 90 degrees and flip horizontally

    First column become first row.
    :param list in_array: a list of arrays

    The transformation is::

        1 2 3       1  4
        4 5 6 7 ->  2  5
                    3  6
                    '' 7
    """
    max_length = longest_row_number(in_array)
    new_array = []
    for i in range(0, max_length):
        row_data = []
        for c in in_array:
            if i < len(c):
                row_data.append(c[i])
            else:
                row_data.append('')
        new_array.append(row_data)
    return new_array


class Matrix(object):
    """The internal representation of a sheet data. Each element
    can be of any python types
    """

    def __init__(self, array):
        """Constructor

        The reason a deep copy was not made here is because
        the data sheet could be huge. It could be costly to
        copy every cell to a new memory area
        :param list array: a list of arrays
        """
        self.__width, self.__array = uniform(list(array))
        self.row = Row(self)
        self.column = Column(self)

    def get_internal_array(self):
        return self.__array

    def number_of_rows(self):
        """The number of rows"""
        return len(self.__array)

    def number_of_columns(self):
        """The number of columns"""
        if self.number_of_rows() > 0:
            return self.__width
        else:
            return 0

    def row_range(self):
        """
        Utility function to get row range
        """
        return compact.irange(0, self.number_of_rows())

    def column_range(self):
        """
        Utility function to get column range
        """
        return compact.irange(0, self.number_of_columns())

    def cell_value(self, row, column, new_value=None):
        """Random access to table cells

        :param int row: row index which starts from 0
        :param int column: column index which starts from 0
        :param any new_value: new value if this is to set the value
        """
        if row in self.row_range() and column in self.column_range():
            if new_value is None:
                # get
                return self.__array[row][column]
            else:
                # set
                self.__array[row][column] = new_value
        else:
            if new_value is None:
                raise IndexError("Index out of range")
            else:
                self.paste((row, column), [[new_value]])

    def row_at(self, index):
        """
        Gets the data at the specified row
        """
        if index in self.row_range():
            return copy.deepcopy(self.__array[index])
        else:
            raise IndexError(constants.MESSAGE_INDEX_OUT_OF_RANGE)

    def set_row_at(self, row_index, data_array):
        """Update a row data range
        """
        nrows = self.number_of_rows()
        if row_index < nrows:
            self.__array[row_index] = data_array
            if len(data_array) != self.number_of_columns():
                self.__width, self.__array = uniform(self.__array)
        else:
            raise IndexError(constants.MESSAGE_INDEX_OUT_OF_RANGE)

    def _set_row_at(self, row_index, data_array, starting=0):
        """Update a row data range

        It works like this if the call is: set_row_at(2, ['N', 'N', 'N'], 1)::

            A B C
            1 3 5
            2 N N <- row_index = 2
              ^starting = 1

        This function will not set element outside the current table range

        :param int row_index: which row to be modified
        :param list data_array: one dimensional array
        :param int starting: from which index, the update happens
        :raises IndexError: if row_index exceeds row range or starting
                            exceeds column range
        """
        nrows = self.number_of_rows()
        ncolumns = self.number_of_columns()
        if row_index < nrows and starting < ncolumns:
            real_len = len(data_array)+starting
            to = min(real_len, ncolumns)
            for i in range(starting, to):
                self.cell_value(row_index, i, data_array[i-starting])
            if real_len > ncolumns:
                left = ncolumns - starting
                self.__array[row_index] = (self.__array[row_index] +
                                           data_array[left:])
            self.__width, self.__array = uniform(self.__array)
        else:
            raise IndexError(constants.MESSAGE_INDEX_OUT_OF_RANGE)

    def _extend_row(self, row):
        array = copy.deepcopy(row)
        self.__array.append(array)

    def extend_rows(self, rows):
        """Inserts two dimensional data after the bottom row"""
        if isinstance(rows, list):
            if compact.is_array_type(rows, list):
                for r in rows:
                    self._extend_row(r)
            else:
                self._extend_row(rows)
            self.__width, self.__array = uniform(self.__array)
        else:
            raise TypeError("Cannot use %s" % type(rows))

    def delete_rows(self, row_indices):
        """Deletes specified row indices"""
        if isinstance(row_indices, list) is False:
            raise IndexError
        if len(row_indices) > 0:
            unique_list = _unique(row_indices)
            sorted_list = sorted(unique_list, reverse=True)
            for i in sorted_list:
                if i < self.number_of_rows():
                    del self.__array[i]

    def column_at(self, index):
        """
        Gets the data at the specified column
        """
        if index in self.column_range():
            cell_array = []
            for i in self.row_range():
                cell_array.append(self.cell_value(i, index))
            return cell_array
        else:
            raise IndexError(constants.MESSAGE_INDEX_OUT_OF_RANGE)

    def set_column_at(self, column_index, data_array, starting=0):
        """Updates a column data range

        It works like this if the call is:
        set_column_at(2, ['N','N', 'N'], 1)::

                +--> column_index = 2
                |
            A B C
            1 3 N <- starting = 1
            2 4 N

        This function will not set element outside the current table range

        :param int column_index: which column to be modified
        :param list data_array: one dimensional array
        :param int staring: from which index, the update happens
        :raises IndexError: if column_index exceeds column range
                            or starting exceeds row range
        """
        nrows = self.number_of_rows()
        ncolumns = self.number_of_columns()
        if column_index < ncolumns and starting < nrows:
            real_len = len(data_array)+starting
            to = min(real_len, nrows)
            for i in range(starting, to):
                self.cell_value(i, column_index, data_array[i-starting])
            if real_len > nrows:
                for i in range(nrows, real_len):
                    new_row = [''] * column_index + [data_array[i-starting]]
                    self.__array.append(new_row)
            self.__width, self.__array = uniform(self.__array)
        else:
            raise IndexError(constants.MESSAGE_INDEX_OUT_OF_RANGE)

    def extend_columns(self, columns):
        """Inserts two dimensional data after the rightmost column

        This is how it works:

        Given::

            s s s     t t

        Get::

            s s s  +  t t
        """
        if not isinstance(columns, list):
            raise TypeError(constants.MESSAGE_DATA_ERROR_DATA_TYPE_MISMATCH)
        incoming_data = columns
        if not compact.is_array_type(columns, list):
            incoming_data = [columns]
        incoming_data = transpose(incoming_data)
        self._extend_columns_with_rows(incoming_data)

    def _extend_columns_with_rows(self, rows):
        current_nrows = self.number_of_rows()
        current_ncols = self.number_of_columns()
        insert_column_nrows = len(rows)
        array_length = min(current_nrows, insert_column_nrows)
        for i in range(0, array_length):
            array = copy.deepcopy(rows[i])
            self.__array[i] += array
        if current_nrows < insert_column_nrows:
            delta = insert_column_nrows - current_nrows
            base = current_nrows
            for i in range(0, delta):
                new_array = [""] * current_ncols
                new_array += rows[base+i]
                self.__array.append(new_array)
        self.__width, self.__array = uniform(self.__array)

    def extend_columns_with_rows(self, rows):
        """Rows were appended to the rightmost side

        example::

            >>> import pyexcel as pe
            >>> data = [
            ...     [1],
            ...     [2],
            ...     [3]
            ... ]
            >>> matrix = pe.sheets.Sheet(data)
            >>> matrix
            pyexcel sheet:
            +---+
            | 1 |
            +---+
            | 2 |
            +---+
            | 3 |
            +---+
            >>> rows = [
            ...      [11, 11],
            ...      [22, 22]
            ... ]
            >>> matrix.extend_columns_with_rows(rows)
            >>> matrix
            pyexcel sheet:
            +---+----+----+
            | 1 | 11 | 11 |
            +---+----+----+
            | 2 | 22 | 22 |
            +---+----+----+
            | 3 |    |    |
            +---+----+----+
        """
        self._extend_columns_with_rows(rows)

    def region(self, topleft_corner, bottomright_corner):
        """Get a rectangle shaped data out

        :param slice topleft_corner: the top left corner of the rectangle
        :param slice bottomright_corner: the bottom right
                                         corner of the rectangle
        """
        region = []
        for row in range(topleft_corner[0], bottomright_corner[0]):
            tmp_row = []
            for column in range(topleft_corner[1], bottomright_corner[1]):
                tmp_row.append(self.cell_value(row, column))
            region.append(tmp_row)
        return region

    def cut(self, topleft_corner, bottomright_corner):
        """Get a rectangle shaped data out and clear them in position

        :param slice topleft_corner: the top left corner of the rectangle
        :param slice bottomright_corner: the bottom right
                                         corner of the rectangle
        """
        region = self.region(topleft_corner, bottomright_corner)
        for row in range(topleft_corner[0], bottomright_corner[0]):
            for column in range(topleft_corner[1], bottomright_corner[1]):
                self.cell_value(row, column, "")
        return region

    def paste(self, topleft_corner, rows=None, columns=None):
        """Paste a rectangle shaped data after a position

        :param slice topleft_corner: the top left corner of the rectangle

        example::

            >>> import pyexcel as pe
            >>> data = [
            ...     # 0 1  2  3  4 5   6
            ...     [1, 2, 3, 4, 5, 6, 7], #  0
            ...     [21, 22, 23, 24, 25, 26, 27],
            ...     [31, 32, 33, 34, 35, 36, 37],
            ...     [41, 42, 43, 44, 45, 46, 47],
            ...     [51, 52, 53, 54, 55, 56, 57]  # 4
            ... ]
            >>> s = pe.Sheet(data)
            >>> # cut  1<= row < 4, 1<= column < 5
            >>> data = s.cut([1, 1], [4, 5])
            >>> s.paste([4,6], rows=data)
            >>> s
            pyexcel sheet:
            +----+----+----+----+----+----+----+----+----+----+
            | 1  | 2  | 3  | 4  | 5  | 6  | 7  |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+
            | 21 |    |    |    |    | 26 | 27 |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+
            | 31 |    |    |    |    | 36 | 37 |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+
            | 41 |    |    |    |    | 46 | 47 |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+
            | 51 | 52 | 53 | 54 | 55 | 56 | 22 | 23 | 24 | 25 |
            +----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    | 32 | 33 | 34 | 35 |
            +----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    | 42 | 43 | 44 | 45 |
            +----+----+----+----+----+----+----+----+----+----+
            >>> s.paste([6,9], columns=data)
            >>> s
            pyexcel sheet:
            +----+----+----+----+----+----+----+----+----+----+----+----+
            | 1  | 2  | 3  | 4  | 5  | 6  | 7  |    |    |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            | 21 |    |    |    |    | 26 | 27 |    |    |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            | 31 |    |    |    |    | 36 | 37 |    |    |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            | 41 |    |    |    |    | 46 | 47 |    |    |    |    |    |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            | 51 | 52 | 53 | 54 | 55 | 56 | 22 | 23 | 24 | 25 |    |    |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    | 32 | 33 | 34 | 35 |    |    |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    | 42 | 43 | 44 | 22 | 32 | 42 |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    |    |    |    | 23 | 33 | 43 |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    |    |    |    | 24 | 34 | 44 |
            +----+----+----+----+----+----+----+----+----+----+----+----+
            |    |    |    |    |    |    |    |    |    | 25 | 35 | 45 |
            +----+----+----+----+----+----+----+----+----+----+----+----+

        """
        if rows:
            starting_row = topleft_corner[0]
            number_of_rows = self.number_of_rows()
            number_of_columns = self.number_of_columns()
            if starting_row > number_of_rows:
                for i in range(0, starting_row - number_of_rows):
                    empty_row = [""] * number_of_columns
                    self._extend_row(empty_row)
            number_of_rows = self.number_of_rows()
            for index, row in enumerate(rows):
                set_index = starting_row + index
                if set_index < number_of_rows:
                    self._set_row_at(set_index, row,
                                     starting=topleft_corner[1])
                else:
                    real_row = [""] * topleft_corner[1] + row
                    self._extend_row(real_row)
            self.__width, self.__array = uniform(self.__array)
        elif columns:
            starting_column = topleft_corner[1]
            number_of_columns = self.number_of_columns()
            for index, column in enumerate(columns):
                set_index = starting_column + index
                if set_index < number_of_columns:
                    self.set_column_at(set_index,
                                       column,
                                       starting=topleft_corner[0])
                else:
                    real_column = [""] * topleft_corner[0] + column
                    self.extend_columns([real_column])
            self.__width, self.__array = uniform(self.__array)
        else:
            raise ValueError(constants.MESSAGE_DATA_ERROR_EMPTY_CONTENT)

    def delete_columns(self, column_indices):
        """Delete columns by specified list of indices
        """
        if isinstance(column_indices, list) is False:
            raise TypeError(constants.MESSAGE_DATA_ERROR_DATA_TYPE_MISMATCH)
        if len(column_indices) > 0:
            unique_list = _unique(column_indices)
            sorted_list = sorted(unique_list, reverse=True)
            for i in self.row_range():
                for j in sorted_list:
                    if j < self.number_of_columns():
                        del self.__array[i][j]
            self.__width = longest_row_number(self.__array)

    def __setitem__(self, aset, c):
        """Override the operator to set items"""
        if isinstance(aset, tuple):
            return self.cell_value(aset[0], aset[1], c)
        elif isinstance(aset, str):
            row, column = utils.excel_cell_position(aset)
            return self.cell_value(row, column, c)
        else:
            raise IndexError

    def __getitem__(self, aset):
        """By default, this class recognize from top to bottom
        from left to right"""
        if isinstance(aset, tuple):
            return self.cell_value(aset[0], aset[1])
        elif isinstance(aset, str):
            row, column = utils.excel_cell_position(aset)
            return self.cell_value(row, column)
        elif isinstance(aset, int):
            print(constants.MESSAGE_DEPRECATED_ROW_COLUMN)
            return self.row_at(aset)
        else:
            raise IndexError

    def contains(self, predicate):
        """Has something in the table"""
        for r in self.rows():
            if predicate(r):
                return True
        else:
            return False

    def transpose(self):
        """Rotate the data table by 90 degrees

        Reference :func:`transpose`
        """
        self.__array = transpose(self.__array)
        self.__width, self.__array = uniform(self.__array)

    def to_array(self):
        """Get an array out
        """
        return self.__array

    def __iter__(self):
        """
        Default iterator to go through each cell one by one from top row to
        bottom row and from left to right
        """
        return self.rows()

    def enumerate(self):
        """
        Iterate cell by cell from top to bottom and from left to right

        .. testcode::

            >>> import pyexcel as pe
            >>> data = [
            ...     [1, 2, 3, 4],
            ...     [5, 6, 7, 8],
            ...     [9, 10, 11, 12]
            ... ]
            >>> m = pe.sheets.Matrix(data)
            >>> print(list(m.enumerate()))
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

        More details see :class:`HTLBRIterator`
        """
        return chain(*self.__array)

    def reverse(self):
        """Opposite to enumerate

        each cell one by one from
        bottom row to top row and from right to left
        example::

            >>> import pyexcel as pe
            >>> data = [
            ...     [1, 2, 3, 4],
            ...     [5, 6, 7, 8],
            ...     [9, 10, 11, 12]
            ... ]
            >>> m = pe.sheets.Matrix(data)
            >>> print(list(m.reverse()))
            [12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]

        More details see :class:`HBRTLIterator`
        """
        for row in reversed(self.__array):
            for cell in reversed(row):
                yield cell

    def vertical(self):
        """
        Default iterator to go through each cell one by one from
        leftmost column to rightmost row and from top to bottom
        example::

            import pyexcel as pe
            data = [
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12]
            ]
            m = pe.Matrix(data)
            print(list(m.vertical()))

        output::

            [1, 5, 9, 2, 6, 10, 3, 7, 11, 4, 8, 12]

        More details see :class:`VTLBRIterator`
        """
        return chain(*compact.czip(*self.__array))

    def rvertical(self):
        """
        Default iterator to go through each cell one by one from rightmost
        column to leftmost row and from bottom to top
        example::

            import pyexcel as pe
            data = [
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12]
            ]
            m = pe.Matrix(data)
            print(pe.utils.to_array(m.rvertical())

        output::

            [12, 8, 4, 11, 7, 3, 10, 6, 2, 9, 5, 1]

        More details see :class:`VBRTLIterator`
        """
        for column in compact.czip(*(reversed(row) for row in self.__array)):
            for cell in reversed(column):
                yield cell

    def rows(self):
        """
        Returns a top to bottom row iterator

        example::

            import pyexcel as pe
            data = [
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12]
            ]
            m = pe.Matrix(data)
            print(pe.utils.to_array(m.rows()))

        output::

            [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]

        More details see :class:`RowIterator`
        """
        for row in self.__array:
            yield row

    def rrows(self):
        """
        Returns a bottom to top row iterator

        .. testcode::

            import pyexcel as pe
            data = [
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12]
            ]
            m = pe.Matrix(data)
            print(pe.utils.to_array(m.rrows()))

        .. testoutput::

            [[9, 10, 11, 12], [5, 6, 7, 8], [1, 2, 3, 4]]

        More details see :class:`RowReverseIterator`
        """
        for row in reversed(self.__array):
            yield row

    def columns(self):
        """
        Returns a left to right column iterator

        .. testcode::

            import pyexcel as pe
            data = [
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12]
            ]
            m = pe.Matrix(data)
            print(list(m.columns()))

        .. testoutput::

            [[1, 5, 9], [2, 6, 10], [3, 7, 11], [4, 8, 12]]

        More details see :class:`ColumnIterator`
        """
        for row in compact.czip(*self.__array):
            yield list(row)

    def rcolumns(self):
        """
        Returns a right to left column iterator

        example::

            import pyexcel as pe
            data = [
                [1, 2, 3, 4],
                [5, 6, 7, 8],
                [9, 10, 11, 12]
            ]
            m = pe.Matrix(data)
            print(pe.utils.to_array(m.rcolumns()))

        output::

            [[4, 8, 12], [3, 7, 11], [2, 6, 10], [1, 5, 9]]

        More details see :class:`ColumnReverseIterator`
        """
        for column in compact.czip(*(reversed(row) for row in self.__array)):
            yield list(column)

    def filter(self, column_indices=None, row_indices=None):
        """Apply the filter with immediate effect"""
        if row_indices is not None:
            self.delete_rows(row_indices)
        if column_indices is not None:
            self.delete_columns(column_indices)

    def format(self, formatter):
        """Apply a formatting action for the whole sheet

        Example::

            >>> import pyexcel as pe
            >>> # Given a dictinoary as the following
            >>> data = {
            ...     "1": [1, 2, 3, 4, 5, 6, 7, 8],
            ...     "3": [1.25, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8],
            ...     "5": [2, 3, 4, 5, 6, 7, 8, 9],
            ...     "7": [1, '',]
            ...     }
            >>> sheet = pe.get_sheet(adict=data)
            >>> sheet.row[1]
            [1, 1.25, 2, 1]
            >>> sheet.format(str)
            >>> sheet.row[1]
            ['1', '1.25', '2', '1']
            >>> sheet.format(int)
            >>> sheet.row[1]
            [1, 1, 2, 1]

        """
        custom_function = partial(to_format, formatter)
        self.map(custom_function)

    def map(self, custom_function):
        """Execute a function across all cells of the sheet

        Example::

            >>> import pyexcel as pe
            >>> # Given a dictinoary as the following
            >>> data = {
            ...     "1": [1, 2, 3, 4, 5, 6, 7, 8],
            ...     "3": [1.25, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8],
            ...     "5": [2, 3, 4, 5, 6, 7, 8, 9],
            ...     "7": [1, '',]
            ...     }
            >>> sheet = pe.get_sheet(adict=data)
            >>> sheet.row[1]
            [1, 1.25, 2, 1]
            >>> inc = lambda value: (float(value) if value != '' else 0)+1
            >>> sheet.map(inc)
            >>> sheet.row[1]
            [2.0, 2.25, 3.0, 2.0]

        """
        for row in self.row_range():
            for column in self.column_range():
                value = self.cell_value(row, column)
                value = custom_function(value)
                self.cell_value(row, column, value)

    def __add__(self, other):
        """Overload the + sign

        :returns: a new book
        """
        from ..book import Book, local_uuid
        content = {}
        content[self.name] = self.__array
        if isinstance(other, Book):
            b = other.to_dict()
            for l in b.keys():
                new_key = l
                if len(b.keys()) == 1:
                    new_key = other._filename
                if new_key in content:
                    uid = local_uuid()
                    new_key = "%s_%s" % (l, uid)
                content[new_key] = b[l]
        elif isinstance(other, Matrix):
            new_key = other.name
            if new_key in content:
                uid = local_uuid()
                new_key = "%s_%s" % (other.name, uid)
            content[new_key] = other.get_internal_array()
        else:
            raise TypeError
        c = Book()
        c.load_from_sheets(content)
        return c

    def __iadd__(self, other):
        """Overload += sign

        :return: self
        """
        raise NotImplementedError(constants.MESSAGE_NOT_IMPLEMENTED_01)

    def add_filter(self, afilter):
        """Apply a filter
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED +
                                  "Please use filter().")

    def remove_filter(self, afilter):
        """Remove a named filter
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def clear_filters(self):
        """Clears all filters"""
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def validate_filters(self):
        """Re-apply filters

        It is called when some data is updated
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def freeze_filters(self):
        """Apply all filters and delete them"""
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def apply_formatter(self, aformatter):
        """Apply the formatter immediately
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def add_formatter(self, aformatter):
        """Add a lazy formatter.
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def remove_formatter(self, aformatter):
        """Remove a formatter

        :param Formatter aformatter: a custom formatter
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def clear_formatters(self):
        """Clear all formatters
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)

    def freeze_formatters(self):
        """Apply all added formatters and clear them
        """
        raise NotImplementedError(constants._IMPLEMENTATION_REMOVED)
