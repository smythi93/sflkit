package de.cispa.sflkitlib;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class ClassMapTests {
    @Test public void integer() {
        assertEquals("int", ClassMap.getPythonType(1));
        assertEquals("int", ClassMap.getPythonType(1L));
        assertEquals("int", ClassMap.getPythonType((short) 1));
        assertEquals("int", ClassMap.getPythonType((byte) 1));
        assertEquals("int", ClassMap.getPythonType('a'));
    }

    @Test public void floatingPoint() {
        assertEquals("float", ClassMap.getPythonType(1.0));
        assertEquals("float", ClassMap.getPythonType(1.0f));
    }

    @Test public void booleanType() {
        assertEquals("bool", ClassMap.getPythonType(true));
    }

    @Test public void string() {
        assertEquals("str", ClassMap.getPythonType("hello"));
    }

    @Test public void byteArray() {
        assertEquals("bytes", ClassMap.getPythonType(new byte[] {1, 2, 3}));
    }

    @Test public void voidType() {
        assertEquals("None", ClassMap.getPythonType(null));
    }
}
