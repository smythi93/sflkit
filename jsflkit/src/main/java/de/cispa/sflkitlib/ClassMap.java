package de.cispa.sflkitlib;

import java.util.HashMap;
import java.util.Map;

public class ClassMap {
    private static final Map<Class<?>, String> javaToPythonClassMap = new HashMap<>();

    static {
        javaToPythonClassMap.put(Integer.class, "int");
        javaToPythonClassMap.put(Long.class, "int");
        javaToPythonClassMap.put(Short.class, "int");
        javaToPythonClassMap.put(Byte.class, "int");
        javaToPythonClassMap.put(Character.class, "int");
        javaToPythonClassMap.put(Double.class, "float");
        javaToPythonClassMap.put(Float.class, "float");
        javaToPythonClassMap.put(Boolean.class, "bool");
        javaToPythonClassMap.put(String.class, "str");
        javaToPythonClassMap.put(byte[].class, "bytes");
        javaToPythonClassMap.put(Void.class, "None");
    }

    public static Class<?> getClass(Object object) {
        if (object == null) {
            return Void.class;
        } else {
            return object.getClass();
        }
    }

    public static String getPythonType(Class<?> clazz) {
        return javaToPythonClassMap.getOrDefault(clazz, clazz.toString());
    }

    public static String getPythonType(Object object) {
        return getPythonType(getClass(object));
    }
}
