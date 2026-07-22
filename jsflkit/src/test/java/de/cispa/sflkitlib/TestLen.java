package de.cispa.sflkitlib;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertTrue;

public class TestLen {

    @Test public void testHasLenCollection() {
        assertTrue(JLib.hasLen(Arrays.asList(new int[] {1, 2, 3})));
    }
}
