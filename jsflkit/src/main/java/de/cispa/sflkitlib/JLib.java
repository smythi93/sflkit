package de.cispa.sflkitlib;

import de.cispa.sflkitlib.events.JCodec;
import de.cispa.sflkitlib.events.JPickle;

import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Collection;

public class JLib {
    private static final String EVENT_TRACE_FILE_PATH = System.getenv("EVENTS_PATH") == null ?
                                                        "EVENTS_PATH" : System.getenv(
            "EVENTS_PATH");

    private static FileOutputStream EVENT_TRACE_FILE;

    static {
        try {
            EVENT_TRACE_FILE = new FileOutputStream(EVENT_TRACE_FILE_PATH);
        } catch (FileNotFoundException e) {
            throw new RuntimeException(e);
        }

        Runtime.getRuntime().addShutdownHook(new Thread(JLib::dump_events));
    }

    public static void dump_events() {
        try {
            EVENT_TRACE_FILE.flush();
            EVENT_TRACE_FILE.close();
        } catch (IOException e) {
            try {
                EVENT_TRACE_FILE.close();
            } catch (IOException ignored) {
            }
        }
    }

    public static void reset() {
        dump_events();
        try {
            EVENT_TRACE_FILE = new FileOutputStream(EVENT_TRACE_FILE_PATH);
        } catch (FileNotFoundException e) {
            throw new RuntimeException(e);
        }
    }

    public static int getID(Object object) {
        return System.identityHashCode(object);
    }

    public static Class<?> getType(Object object) {
        return object.getClass();
    }

    private static void write(byte[] encodedEvent) {
        try {
            EVENT_TRACE_FILE.write(encodedEvent);
        } catch (IOException ignored) {
        }
    }

    public static void addLineEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addBranchEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addDefEvent(int eventID, int varID, Object value) {
        write(JCodec.encodeDefEvent(
                eventID, varID, JPickle.pickle(value), ClassMap.getPythonType(value)));
    }

    public static void addFunctionEnterEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addFunctionExitEvent(int eventID, Object returnValue) {
        write(JCodec.encodeFunctionExitEvent(
                eventID, JPickle.pickle(returnValue), ClassMap.getPythonType(returnValue)));
    }

    public static void addFunctionErrorEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addConditionEvent(int eventID, boolean condition) {
        write(JCodec.encodeConditionEvent(eventID, condition));
    }

    public static void addLoopBeginEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addLoopHitEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addLoopEndEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addUseEvent(int eventID, int varID) {
        write(JCodec.encodeUseEvent(eventID, varID));
    }

    public static int getLen(Collection<?> object) {
        return object.size();
    }

    public static int getLen(Object[] object) {
        return object.length;
    }

    public static int getLen(byte[] object) {
        return object.length;
    }

    public static int getLen(short[] object) {
        return object.length;
    }

    public static int getLen(int[] object) {
        return object.length;
    }

    public static int getLen(long[] object) {
        return object.length;
    }

    public static int getLen(float[] object) {
        return object.length;
    }

    public static int getLen(double[] object) {
        return object.length;
    }

    public static int getLen(char[] object) {
        return object.length;
    }

    public static int getLen(boolean[] object) {
        return object.length;
    }

    public static int getLen(String object) {
        return object.length();
    }

    public static boolean hasLen(Collection<?> ignored) {
        return true;
    }

    public static boolean hasLen(Object[] ignored) {
        return true;
    }

    public static boolean hasLen(byte[] ignored) {
        return true;
    }

    public static boolean hasLen(short[] ignored) {
        return true;
    }

    public static boolean hasLen(int[] ignored) {
        return true;
    }

    public static boolean hasLen(long[] ignored) {
        return true;
    }

    public static boolean hasLen(float[] ignored) {
        return true;
    }

    public static boolean hasLen(double[] ignored) {
        return true;
    }

    public static boolean hasLen(char[] ignored) {
        return true;
    }

    public static boolean hasLen(boolean[] ignored) {
        return true;
    }

    public static boolean hasLen(String ignored) {
        return true;
    }

    public static boolean hasLen(Object ignored) {
        return false;
    }

    public static void addLenEvent(int eventID, int varID, int length) {
        write(JCodec.encodeLenEvent(eventID, varID, length));
    }

    public static void addTestStartEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addTestEndEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addTestLineEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }

    public static void addTestDefEvent(int eventID, int varID) {
        write(JCodec.encodeBaseDefEvent(eventID, varID));
    }

    public static void addTestUseEvent(int eventID, int varID) {
        write(JCodec.encodeUseEvent(eventID, varID));
    }

    public static void addTestAssertEvent(int eventID) {
        write(JCodec.encodeEvent(eventID));
    }
}
