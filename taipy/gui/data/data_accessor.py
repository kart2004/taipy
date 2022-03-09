import inspect
import typing as t
import warnings
from abc import ABC, abstractmethod

from ..utils import _TaipyData
from .data_format import _DataFormat


class _DataAccessor(ABC):

    _WS_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    @staticmethod
    @abstractmethod
    def get_supported_classes() -> t.List[str]:
        pass

    @abstractmethod
    def get_data(
        self, guiApp: t.Any, var_name: str, value: t.Any, payload: t.Dict[str, t.Any], data_format: _DataFormat
    ) -> t.Dict[str, t.Any]:
        pass

    @abstractmethod
    def get_col_types(self, var_name: str, value: t.Any) -> t.Dict[str, str]:
        pass


class _InvalidDataAccessor(_DataAccessor):
    @staticmethod
    def get_supported_classes() -> t.List[str]:
        return [type(None).__name__]

    def get_data(
        self, guiApp: t.Any, var_name: str, value: t.Any, payload: t.Dict[str, t.Any], data_format: _DataFormat
    ) -> t.Dict[str, t.Any]:
        return {}

    def get_col_types(self, var_name: str, value: t.Any) -> t.Dict[str, str]:
        return {}


class _DataAccessors(object):
    def __init__(self) -> None:
        self.__access_4_type: t.Dict[str, _DataAccessor] = {}

        self.__invalid_data_accessor = _InvalidDataAccessor()

        self.__data_format = _DataFormat.JSON

        from .array_dict_data_accessor import _ArrayDictDataAccessor
        from .numpy_data_accessor import _NumpyDataAccessor
        from .pandas_data_accessor import _PandasDataAccessor

        self._register(_PandasDataAccessor)
        self._register(_ArrayDictDataAccessor)
        self._register(_NumpyDataAccessor)

    def _register(self, cls: t.Type[_DataAccessor]) -> None:
        if inspect.isclass(cls):
            if issubclass(cls, _DataAccessor):
                names = cls.get_supported_classes()
                if not names:
                    raise TypeError(f"method {cls.__name__}.get_supported_classes returned an invalid value")
                # check existence
                inst: t.Optional[_DataAccessor] = None
                for name in names:
                    inst = self.__access_4_type.get(name)
                    if inst:
                        break
                if inst is None:
                    try:
                        inst = cls()
                    except Exception as e:
                        raise TypeError(f"Class {cls.__name__} cannot be instanciated") from e
                    if inst:
                        for name in names:
                            self.__access_4_type[name] = inst  # type: ignore
            else:
                raise TypeError(f"Class {cls.__name__} is not a subclass of DataAccessor")
        else:
            raise AttributeError("The argument of 'DataAccessors.register' should be a class")

    def __get_instance(self, value: _TaipyData) -> _DataAccessor:  # type: ignore
        value = value.get()
        access = self.__access_4_type.get(type(value).__name__)
        if access is None:
            warnings.warn(f"Can't find Data Accessor for type {type(value).__name__}")
            return self.__invalid_data_accessor
        return access

    def _get_data(
        self, guiApp: t.Any, var_name: str, value: _TaipyData, payload: t.Dict[str, t.Any]
    ) -> t.Dict[str, t.Any]:
        return self.__get_instance(value).get_data(guiApp, var_name, value.get(), payload, self.__data_format)

    def _get_col_types(self, var_name: str, value: _TaipyData) -> t.Dict[str, str]:
        return self.__get_instance(value).get_col_types(var_name, value.get())

    def _set_data_format(self, data_format: _DataFormat):
        self.__data_format = data_format
