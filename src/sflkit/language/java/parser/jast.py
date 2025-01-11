import abc
from typing import List


class JAST(abc.ABC):
    pass


class _JAST(JAST, abc.ABC):
    def __init__(
        self,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        self.lineno = lineno
        self.col_offset = col_offset
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset

    def __hash__(self):
        return hash(id(self))


# Simple Types
class Type(_JAST, abc.ABC):
    pass


class PrimitiveType(Type, abc.ABC):
    pass


class Boolean(PrimitiveType):
    pass


class Char(PrimitiveType):
    pass


class Byte(PrimitiveType):
    pass


class Short(PrimitiveType):
    pass


class Int(PrimitiveType):
    pass


class Long(PrimitiveType):
    pass


class Float(PrimitiveType):
    pass


class Double(PrimitiveType):
    pass


class Void(PrimitiveType):
    pass


# Names


class Identifier(_JAST):
    def __init__(
        self,
        id_: str = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.id = id_


class QualifiedName(_JAST):
    def __init__(
        self,
        identifiers: List[Identifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.identifiers = identifiers or []


class AltAnnotationQualifiedName(_JAST):
    def __init__(
        self,
        identifiers: List[Identifier] = None,
        identifier: Identifier = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.identifiers = identifiers or []
        self.identifier = identifier


class VariableDeclaratorId(_JAST):
    def __init__(
        self,
        identifier: Identifier = None,
        brackets: int = 0,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.brackets = brackets


# Expressions


class Expression(_JAST, abc.ABC):
    pass


class Arguments(_JAST):
    def __init__(
        self,
        expressions: List[Expression] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.expressions = expressions or []


class VariableInitializer(_JAST):
    def __init__(
        self,
        value: Expression | "ArrayInitializer" = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if value is None:
            raise ValueError("value cannot be None")
        self.value = value


class ArrayInitializer(_JAST):
    def __init__(
        self,
        initializers: List[VariableInitializer] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.initializers = initializers or []


# ElementValues


class ElementValue(_JAST):
    def __init__(
        self,
        value: Expression | "Annotation" | "ElementValueArrayInitializer" = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if value is None:
            raise ValueError("value cannot be None")
        self.value = value


class ElementValueArrayInitializer(_JAST):
    def __init__(
        self,
        element_values: List[ElementValue] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.element_values = element_values or []


class ElementValuePair(_JAST):
    def __init__(
        self,
        identifier: Identifier = None,
        element_value: ElementValue = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.element_value = element_value


class ElementValuePairs(_JAST):
    def __init__(
        self,
        element_values: List[ElementValuePair] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.element_values = element_values or []


# Modifiers


class Modifier(_JAST, abc.ABC):
    pass


class TRANSITIVE(Modifier):
    pass


class STATIC(Modifier):
    pass


class PUBLIC(Modifier):
    pass


class PROTECTED(Modifier):
    pass


class PRIVATE(Modifier):
    pass


class ABSTRACT(Modifier):
    pass


class FINAL(Modifier):
    pass


class STRICTFP(Modifier):
    pass


class SEALED(Modifier):
    pass


# noinspection PyPep8Naming
class NON_SEALED(Modifier):
    pass


class DEFAULT(Modifier):
    pass


class Annotation(_JAST):
    def __init__(
        self,
        qualified_name: QualifiedName | AltAnnotationQualifiedName = None,
        element_values: ElementValuePairs | ElementValue = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name
        self.element_values = element_values


class Annotations(JAST):
    def __init__(
        self,
        annotations: List[Annotation] = None,
    ):
        self.annotations = annotations or []


ClassOrInterfaceModifier = (
    Annotation
    | PUBLIC
    | PROTECTED
    | PRIVATE
    | ABSTRACT
    | STATIC
    | FINAL
    | STRICTFP
    | SEALED
    | NON_SEALED
)

VariableModifier = FINAL | Annotation

InterfaceMethodModifier = Annotation | PUBLIC | ABSTRACT | DEFAULT | STATIC | STRICTFP

# Complex Types


class ClassOrInterfaceType(Type):
    pass  # TODO


class TypeType(_JAST):
    def __init__(
        self,
        annotations: Annotations = None,
        type_: Type = None,
        brackets_annotations: Annotations = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.annotations = annotations
        self.type_ = type_
        self.brackets_annotations = brackets_annotations


class TypeParameter(_JAST):
    def __init__(
        self,
        annotations: List[Annotation] = None,
        identifier: Identifier = None,
        extends: List[TypeType] = None,
        extends_annotations: List[Annotation] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.extends = extends or []
        self.extends_annotations = extends_annotations or []
        self.annotations = annotations or []


# Parameters


class ReceiverParameter(_JAST):
    def __init__(
        self,
        type_: TypeType = None,
        identifiers: List[Identifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        self.identifiers = identifiers or []


class FormalParameter(_JAST):
    def __init__(
        self,
        modifiers: List[VariableModifier] = None,
        type_: TypeType = None,
        variable_declarator_id: VariableDeclaratorId = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.modifiers = modifiers or []
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        if variable_declarator_id is None:
            raise ValueError("variable_declarator_id cannot be None")
        self.variable_declarator_id = variable_declarator_id


class LastFormalParameter(_JAST):
    def __init__(
        self,
        modifiers: List[VariableModifier] = None,
        type_: TypeType = None,
        annotations: Annotations = None,
        variable_declarator_id: VariableDeclaratorId = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.modifiers = modifiers or []
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        self.annotations = annotations
        if variable_declarator_id is None:
            raise ValueError("variable_declarator_id cannot be None")
        self.variable_declarator_id = variable_declarator_id


class FormalParameterList(_JAST):
    def __init__(
        self,
        parameters: List[FormalParameter] = None,
        last: LastFormalParameter = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if not parameters and not last:
            raise ValueError("parameters and last cannot be None at the same time")
        self.parameters = parameters or []
        self.last = last


class FormalParameters(_JAST):
    def __init__(
        self,
        receiver_parameter: ReceiverParameter = None,
        parameters: FormalParameterList = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.receiver_parameter = receiver_parameter
        self.parameters = parameters


# Statements
class Stmt(_JAST, abc.ABC):
    pass


class StaticBlock(_JAST):
    def __init__(
        self,
        body: List["BlockStatement"] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.body = body or []


# Declarations


class Declaration(_JAST, abc.ABC):
    pass


class PackageDeclaration(_JAST):
    def __init__(
        self,
        annotations: Annotations = None,
        qualified_name: QualifiedName = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.annotations = annotations
        self.qualified_name = qualified_name


class ImportDeclaration(_JAST):
    def __init__(
        self,
        static: bool = False,
        qualified_name: QualifiedName = None,
        star: bool = False,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.static = static
        self.qualified_name = qualified_name
        self.star = star


class TypeDeclaration(Declaration, abc.ABC):
    def __init__(
        self,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.modifiers = modifiers or []


class ClassDeclaration(TypeDeclaration):
    def __init__(
        self,
        identifier: Identifier = None,
        type_parameters: List[TypeParameter] = None,
        extends: TypeType = None,
        implements: List[TypeType] = None,
        permits: List[TypeType] = None,
        body: List[Stmt] = None,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.type_parameters = type_parameters or []
        self.extends = extends
        self.implements = implements or []
        self.permits = permits or []
        self.body = body or []


class EnumConstant(_JAST):
    def __init__(
        self,
        annotations: Annotations = None,
        identifier: Identifier = None,
        arguments: Arguments = None,
        body: List[Declaration] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.annotations = annotations or []
        self.identifier = identifier
        self.arguments = arguments or []
        self.body = body or []


class EnumDeclaration(TypeDeclaration):
    def __init__(
        self,
        identifier: Identifier = None,
        implements: List[TypeType] = None,
        enum_constants: List[EnumConstant] = None,
        body: List[Declaration] = None,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.implements = implements or []
        self.enum_constants = enum_constants or []
        self.body = body or []


class InterfaceDeclaration(TypeDeclaration):
    def __init__(
        self,
        identifier: Identifier = None,
        type_parameters: List[TypeParameter] = None,
        extends: List[TypeType] = None,
        permits: List[TypeType] = None,
        body: List["InterfaceBodyDeclaration"] = None,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.type_parameters = type_parameters or []
        self.extends = extends or []
        self.permits = permits or []
        self.body = body or []


class VariableDeclarator(_JAST):
    def __init__(
        self,
        variable_declarator_id: VariableDeclaratorId = None,
        initializer: VariableInitializer = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if variable_declarator_id is None:
            raise ValueError("variable_declarator_id cannot be None")
        self.variable_declarator_id = variable_declarator_id
        self.initializer = initializer


class VariableDeclarators(_JAST):
    def __init__(
        self,
        declarators: List[VariableDeclarator] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.declarators = declarators or []


class LocalVariableDeclaration(Declaration):
    def __init__(
        self,
        type_: TypeType = None,
        variable_declarators: VariableDeclarators = None,
        modifiers: List[VariableModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        self.variable_declarators = variable_declarators
        self.modifiers = modifiers or []


class VarDeclaration(Declaration):
    def __init__(
        self,
        identifier: Identifier = None,
        expr: Expression = None,
        modifiers: List[VariableModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        if expr is None:
            raise ValueError("expr cannot be None")
        self.expr = expr
        self.modifiers = modifiers or []


class AnnotationTypeMethodRest(_JAST):
    def __init__(
        self,
        type_: TypeType = None,
        identifier: Identifier = None,
        default: ElementValue = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.default = default


class AnnotationTypeConstantRest(_JAST):
    def __init__(
        self,
        type_: TypeType = None,
        variable_declarators: VariableDeclarators = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        self.variable_declarators = variable_declarators


class AnnotationTypeDeclaration(TypeDeclaration):
    def __init__(
        self,
        identifier: Identifier = None,
        body: List["AnnotationTypeElementRest"] = None,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.body = body or []


class RecordComponent(_JAST):
    def __init__(
        self,
        type_: TypeType = None,
        identifier: Identifier = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier


class RecordHeader(_JAST):
    def __init__(
        self,
        components: List[RecordComponent] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.components = components or []


class RecordDeclaration(TypeDeclaration):
    def __init__(
        self,
        identifier: Identifier = None,
        type_parameters: List[TypeParameter] = None,
        record_header: RecordHeader = None,
        implements: List[TypeType] = None,
        body: List["RecordBodyElement"] = None,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.type_parameters = type_parameters or []
        self.record_header = record_header
        self.implements = implements or []
        self.body = body or []


class ModifierDeclaration(Declaration):
    def __init__(
        self,
        modifiers: List[Modifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.modifiers = modifiers or []


class MethodDeclaration(ModifierDeclaration):
    def __init__(
        self,
        type_parameters: List[TypeParameter] = None,
        return_type: TypeType = None,
        identifier: Identifier = None,
        parameters: FormalParameters = None,
        brackets: int = 0,
        throws: List[QualifiedName] = None,
        body: List[Stmt] = None,
        modifiers: List[Modifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        if return_type is None:
            raise ValueError("return_type cannot be None")
        self.type_parameters = type_parameters or []
        self.return_type = return_type
        self.identifier = identifier
        self.parameters = parameters or []
        self.brackets = brackets
        self.throws = throws or []
        self.body = body or []
        self.modifiers = modifiers or []


class ConstructorDeclaration(ModifierDeclaration):
    def __init__(
        self,
        type_parameters: List[TypeParameter] = None,
        identifier: Identifier = None,
        parameters: FormalParameters = None,
        throws: List[QualifiedName] = None,
        body: List[Stmt] = None,
        modifiers: List[Modifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.type_parameters = type_parameters or []
        self.identifier = identifier
        self.parameters = parameters or []
        self.throws = throws or []
        self.body = body or []
        self.modifiers = modifiers or []


class FieldDeclaration(ModifierDeclaration):
    def __init__(
        self,
        type_: TypeType = None,
        declarators: List[VariableDeclarator] = None,
        modifiers: List[Modifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        self.declarators = declarators or []
        self.modifiers = modifiers or []


MemberDeclaration = (
    RecordDeclaration
    | MethodDeclaration
    | FieldDeclaration
    | ConstructorDeclaration
    | InterfaceDeclaration
    | AnnotationTypeDeclaration
    | ClassDeclaration
    | EnumDeclaration
)

ClassBodyDeclaration = StaticBlock | MemberDeclaration


class ConstantDeclarator(_JAST):
    def __init__(
        self,
        identifier: Identifier = None,
        brackets: int = 0,
        initializer: VariableInitializer = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.brackets = brackets
        self.initializer = initializer


class ConstDeclaration(ModifierDeclaration):
    def __init__(
        self,
        type_: TypeType = None,
        declarators: List[ConstantDeclarator] = None,
        modifiers: List[Modifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset, modifiers)
        if type_ is None:
            raise ValueError("type_ cannot be None")
        self.type_ = type_
        self.declarators = declarators or []


class InterfaceCommonBodyDeclaration(_JAST):
    def __init__(
        self,
        annotations: Annotations = None,
        type_: TypeType | Void = None,
        identifier: Identifier = None,
        parameters: FormalParameters = None,
        brackets: int = 0,
        throws: List[QualifiedName] = None,
        body: List["BlockStatement"] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.annotations = annotations
        self.type_ = type_
        self.identifier = identifier
        self.parameters = parameters
        self.brackets = brackets
        self.throws = throws or []
        self.body = body or []


class InterfaceMethodDeclaration(ModifierDeclaration):
    def __init__(
        self,
        modifiers: List[InterfaceMethodModifier] = None,
        type_parameters: List[TypeParameter] = None,
        interface_common_body_declaration: InterfaceCommonBodyDeclaration = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        self.type_parameters = type_parameters or []
        self.interface_common_body_declaration = interface_common_body_declaration


InterfaceBodyDeclaration = (
    RecordDeclaration
    | ConstDeclaration
    | InterfaceMethodDeclaration
    | InterfaceDeclaration
    | AnnotationTypeDeclaration
    | ClassDeclaration
    | EnumDeclaration
)

AnnotationTypeElementRest = (
    AnnotationTypeMethodRest
    | AnnotationTypeConstantRest
    | ClassDeclaration
    | InterfaceDeclaration
    | EnumDeclaration
    | AnnotationTypeDeclaration
    | RecordDeclaration
)


class CompactConstructorDeclaration(ModifierDeclaration):
    def __init__(
        self,
        identifier: Identifier = None,
        body: List["BlockStatement"] = None,
        modifiers: List[Modifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(modifiers, lineno, col_offset, end_lineno, end_col_offset)
        if identifier is None:
            raise ValueError("identifier cannot be None")
        self.identifier = identifier
        self.body = body or []


RecordBodyElement = ClassBodyDeclaration | CompactConstructorDeclaration


class LocalTypeDeclaration(_JAST):
    def __init__(
        self,
        declaration: ClassDeclaration | InterfaceDeclaration | RecordDeclaration,
        modifiers: List[ClassOrInterfaceModifier] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if declaration is None:
            raise ValueError("declaration cannot be None")
        self.declaration = declaration
        self.modifiers = modifiers or []


BlockStatement = Stmt | LocalVariableDeclaration | VarDeclaration | LocalTypeDeclaration

# ModuleNodes


class ModuleDirective(_JAST, abc.ABC):
    pass


class RequiresDirective(ModuleDirective):
    def __init__(
        self,
        modifiers: List[TRANSITIVE | STATIC] = None,
        qualified_name: QualifiedName = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.modifiers = modifiers or []
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name


class ExportsDirective(ModuleDirective):
    def __init__(
        self,
        qualified_name: QualifiedName = None,
        to: QualifiedName = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name
        self.to = to


class OpensDirective(ModuleDirective):
    def __init__(
        self,
        qualified_name: QualifiedName = None,
        to: QualifiedName = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name
        self.to = to


class UsesDirective(ModuleDirective):
    def __init__(
        self,
        qualified_name: QualifiedName = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name


class ProvidesDirective(ModuleDirective):
    def __init__(
        self,
        qualified_name: QualifiedName = None,
        with_: List[QualifiedName] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name
        self.with_ = with_ or []


class CompilationUnit(_JAST, abc.ABC):
    pass


class ModuleDeclaration(CompilationUnit):
    def __init__(
        self,
        open_: bool = False,
        qualified_name: QualifiedName = None,
        module_directives: List[ModuleDirective] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.open = open_
        if qualified_name is None:
            raise ValueError("qualified_name cannot be None")
        self.qualified_name = qualified_name
        self.module_directives = module_directives or []


class Module(CompilationUnit):
    def __init__(
        self,
        package_declaration: PackageDeclaration = None,
        import_declarations: List[ImportDeclaration] = None,
        type_declarations: List[TypeDeclaration] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.package_declaration = package_declaration
        self.import_declarations = import_declarations or []
        self.type_declarations = type_declarations or []


class StaticBlock(Declaration):
    def __init__(
        self,
        body: List[Stmt] = None,
        lineno: int = None,
        col_offset: int = None,
        end_lineno: int = None,
        end_col_offset: int = None,
    ):
        super().__init__(lineno, col_offset, end_lineno, end_col_offset)
        self.body = body or []
