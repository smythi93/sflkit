from sflkit.language.java.parser import jast
from sflkit.language.java.parser.JavaParser import JavaParser
from sflkit.language.java.parser.JavaParserVisitor import JavaParserVisitor


class JavaASTBuilder(JavaParserVisitor):
    def visitCompilationUnit(
        self, ctx: JavaParser.CompilationUnitContext
    ) -> jast.CompilationUnit:
        if ctx.moduleDeclaration():
            return self.visitModuleDeclaration(ctx.moduleDeclaration())
        else:
            return jast.Module(
                package_declaration=self.visitPackageDeclaration(
                    ctx.packageDeclaration()
                )
                if ctx.packageDeclaration()
                else None,
                import_declarations=[
                    self.visitImportDeclaration(i) for i in ctx.importDeclaration()
                ]
                if ctx.importDeclaration()
                else [],
                type_declarations=[
                    self.visitTypeDeclaration(t) for t in ctx.typeDeclaration()
                ]
                if ctx.typeDeclaration()
                else [],
            )

    def visitModuleDeclaration(
        self, ctx: JavaParser.ModuleDeclarationContext
    ) -> jast.ModuleDeclaration:
        return jast.ModuleDeclaration(
            open_=ctx.OPEN() is not None,
            qualified_name=self.visitQualifiedName(ctx.qualifiedName()),
            module_directives=self.visitModuleBody(ctx.moduleBody()),
            lineno=ctx.start.line,
            col_offset=ctx.start.column,
            end_lineno=ctx.stop.line,
            end_col_offset=ctx.stop.column,
        )

    def visitModuleBody(
        self, ctx: JavaParser.ModuleBodyContext
    ) -> list[jast.ModuleDirective]:
        return [self.visitModuleDirective(d) for d in ctx.moduleDirective()]

    def visitModuleDirective(
        self, ctx: JavaParser.ModuleDirectiveContext
    ) -> jast.ModuleDirective:
        kwargs = {
            "lineno": ctx.start.line,
            "col_offset": ctx.start.column,
            "end_lineno": ctx.stop.line,
            "end_col_offset": ctx.stop.column,
        }
        if ctx.REQUIRES():
            return jast.RequiresDirective(
                modifiers=[
                    self.visitRequiresModifier(m) for m in ctx.requiresModifier()
                ],
                qualified_name=self.visitQualifiedName(ctx.qualifiedName(0)),
                **kwargs,
            )
        elif ctx.EXPORTS():
            return jast.ExportsDirective(
                qualified_name=self.visitQualifiedName(ctx.qualifiedName(0)),
                to=self.visitQualifiedName(ctx.qualifiedName(1)) if ctx.TO() else None,
                **kwargs,
            )
        elif ctx.OPENS():
            return jast.OpensDirective(
                qualified_name=self.visitQualifiedName(ctx.qualifiedName(0)),
                to=self.visitQualifiedName(ctx.qualifiedName(1)) if ctx.TO() else None,
                **kwargs,
            )
        elif ctx.USES():
            return jast.UsesDirective(
                qualified_name=self.visitQualifiedName(ctx.qualifiedName(0)), **kwargs
            )
        elif ctx.PROVIDES():
            return jast.ProvidesDirective(
                qualified_name=self.visitQualifiedName(ctx.qualifiedName(0)),
                with_=self.visitQualifiedName(ctx.qualifiedName(1)),
                **kwargs,
            )
        else:
            raise ValueError("Invalid module directive")

    def visitRequiresModifier(
        self, ctx: JavaParser.RequiresModifierContext
    ) -> jast.TRANSITIVE | jast.STATIC:
        if ctx.STATIC():
            return jast.STATIC()
        elif ctx.TRANSITIVE():
            return jast.TRANSITIVE()
        else:
            raise ValueError("Invalid requires modifier")

    def visitPackageDeclaration(
        self, ctx: JavaParser.PackageDeclarationContext
    ) -> jast.PackageDeclaration:
        return jast.PackageDeclaration(
            annotations=[self.visitAnnotation(a) for a in ctx.annotation()]
            if ctx.annotation()
            else [],
            qualified_name=self.visitQualifiedName(ctx.qualifiedName()),
            lineno=ctx.start.line,
            col_offset=ctx.start.column,
            end_lineno=ctx.stop.line,
            end_col_offset=ctx.stop.column,
        )

    def visitImportDeclaration(
        self, ctx: JavaParser.ImportDeclarationContext
    ) -> jast.ImportDeclaration:
        return jast.ImportDeclaration(
            static=ctx.STATIC() is not None,
            qualified_name=self.visitQualifiedName(ctx.qualifiedName()),
            star=ctx.MUL() is not None,
            lineno=ctx.start.line,
            col_offset=ctx.start.column,
            end_lineno=ctx.stop.line,
            end_col_offset=ctx.stop.column,
        )

    def visitTypeDeclaration(
        self, ctx: JavaParser.TypeDeclarationContext
    ) -> jast.TypeDeclaration:
        modifiers = [self.visitModifier(m) for m in ctx.classOrInterfaceModifier()]
        if ctx.classDeclaration():
            declaration = self.visitClassDeclaration(ctx.classDeclaration())
        elif ctx.enumDeclaration():
            declaration = self.visitInterfaceDeclaration(ctx.interfaceDeclaration())
        elif ctx.interfaceDeclaration():
            declaration = self.visitInterfaceDeclaration(ctx.interfaceDeclaration())
        elif ctx.annotationTypeDeclaration():
            declaration = self.visitAnnotationTypeDeclaration(
                ctx.annotationTypeDeclaration()
            )
        elif ctx.recordDeclaration():
            declaration = self.visitRecordDeclaration(ctx.recordDeclaration())
        else:
            raise ValueError("Invalid type declaration")
        declaration.modifiers = modifiers
        return declaration

    def visitModifier(self, ctx: JavaParser.ModifierContext) -> jast.Modifier:
        if ctx.classOrInterfaceModifier():
            return self.visitClassOrInterfaceModifier(ctx.classOrInterfaceModifier())
        elif ctx.NATIVE():
            return jast.Native()
        elif ctx.SYNCHRONIZED():
            return jast.Synchronized()
        elif ctx.TRANSIENT():
            return jast.Transient()
        elif ctx.VOLATILE():
            return jast.Volatile()
        else:
            raise ValueError("Invalid modifier")

    def visitClassOrInterfaceModifier(
        self, ctx: JavaParser.ClassOrInterfaceModifierContext
    ) -> jast.ClassOrInterfaceModifier:
        if ctx.annotation():
            return self.visitAnnotation(ctx.annotation())
        elif ctx.PUBLIC():
            return jast.Public()
        elif ctx.PROTECTED():
            return jast.Protected()
        elif ctx.PRIVATE():
            return jast.Private()
        elif ctx.STATIC():
            return jast.Static()
        elif ctx.ABSTRACT():
            return jast.Abstract()
        elif ctx.STATIC():
            return jast.Static()
        elif ctx.FINAL():
            return jast.Final()
        elif ctx.STRICTFP():
            return jast.Strictfp()
        elif ctx.SEALED():
            return jast.Sealed()
        elif ctx.NON_SEALED():
            return jast.NonSealed()
        else:
            raise ValueError("Invalid class or interface modifier")

    def visitVariableModifier(
        self, ctx: JavaParser.VariableModifierContext
    ) -> jast.VariableModifier:
        if ctx.FINAL():
            return jast.Final()
        elif ctx.annotation():
            return self.visitAnnotation(ctx.annotation())
        else:
            raise ValueError("Invalid variable modifier")

    def visitClassDeclaration(
        self, ctx: JavaParser.ClassDeclarationContext
    ) -> jast.ClassDeclaration:
        if ctx.IMPLEMENTS():
            if ctx.PERMITS():
                implements = self.visitTypeList(ctx.typeList(0))
                permits = self.visitTypeList(ctx.typeList(1))
            else:
                implements = self.visitTypeList(ctx.typeList(0))
                permits = []
        elif ctx.PERMITS():
            implements = []
            permits = self.visitTypeList(ctx.typeList(0))
        else:
            implements = []
            permits = []
        return jast.ClassDeclaration(
            identifier=self.visitIdentifier(ctx.identifier()),
            type_parameters=self.visitTypeParameters(ctx.typeParameters())
            if ctx.typeParameters()
            else [],
            extends=self.visitTypeType(ctx.typeType())
            if ctx.EXTENDS()
            else None
            if ctx.typeList()
            else [],
            implements=implements,
            permits=permits,
            body=self.visitClassBody(ctx.classBody()),
            lineno=ctx.start.line,
            col_offset=ctx.start.column,
            end_lineno=ctx.stop.line,
            end_col_offset=ctx.stop.column,
        )

    def visitTypeParameters(self, ctx: JavaParser.TypeParametersContext):
        return [self.visitTypeParameter(p) for p in ctx.typeParameter()]

    def visitTypeParameter(self, ctx: JavaParser.TypeParameterContext):
        all_annotations = (
            [self.visitAnnotation(a) for a in ctx.annotation()]
            if ctx.annotation()
            else []
        )
        annotations = []
        extends_annotations = []
        if ctx.EXTENDS():
            line, col = ctx.EXTENDS().start.line, ctx.EXTENDS().start.column
            for annotation in all_annotations:
                if annotation.lineno < line or (
                    annotation.lineno == line and annotation.col_offset < col
                ):
                    annotations.append(annotation)
                else:
                    extends_annotations.append(annotation)
        else:
            annotations = all_annotations
        return jast.TypeParameter(
            identifier=self.visitIdentifier(ctx.identifier()),
            annotations=annotations,
            extends=self.visitTypeBound(ctx.typeBound()) if ctx.typeBound() else [],
            extends_annotations=extends_annotations,
            lineno=ctx.start.line,
            col_offset=ctx.start.column,
            end_lineno=ctx.stop.line,
            end_col_offset=ctx.stop.column,
        )
