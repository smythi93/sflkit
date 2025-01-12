from sflkit.language.extract import VariableExtract, ConditionExtract
import jast


class JavaVarExtract(jast.JNodeVisitor, VariableExtract):
    pass


class JavaConditionExtract(jast.JNodeVisitor, ConditionExtract):
    pass