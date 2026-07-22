package de.cispa.sflkitlib;

import de.cispa.sflkitlib.events.JCodec;
import de.cispa.sflkitlib.events.JPickle;

import java.io.BufferedOutputStream;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.util.Collection;

public class JLib {
    private static final String EVENT_TRACE_FILE_PATH = System.getenv("EVENTS_PATH") == null ?
                                                        "EVENTS_PATH" : System.getenv(
            "EVENTS_PATH");

    private static OutputStream EVENT_TRACE_FILE;

    // Cap the number of events written per execution (EVENTS_MAX env var, 0 or
    // unset = unlimited).  Loop-heavy code (e.g. numeric kernels) can emit tens
    // of millions of events for a single test; once every feature has occurred,
    // the extra repetitions only bloat the trace and slow the run (they even
    // cause timeouts).  After the cap, events are dropped but the program runs
    // on normally, so its pass/fail outcome is unchanged.
    private static final long EVENTS_MAX = parseEventsMax();
    private static volatile long eventCount = 0;

    private static long parseEventsMax() {
        String value = System.getenv("EVENTS_MAX");
        if (value == null || value.trim().isEmpty()) {
            return Long.MAX_VALUE;
        }
        try {
            long parsed = Long.parseLong(value.trim());
            return parsed <= 0 ? Long.MAX_VALUE : parsed;
        } catch (NumberFormatException e) {
            return Long.MAX_VALUE;
        }
    }

    // When EVENTS_THREADS is set, every event is prefixed with the id of the
    // writing thread (matching the Python codec's optional thread_id prefix), so
    // multi-threaded executions can be disentangled.  Writes are serialized so
    // that a thread prefix and its event stay together.
    private static final boolean THREAD_SUPPORT =
            "1".equals(System.getenv("EVENTS_THREADS"))
                    || "true".equalsIgnoreCase(System.getenv("EVENTS_THREADS"));
    private static final Object LOCK = new Object();

    static {
        try {
            EVENT_TRACE_FILE = new BufferedOutputStream(
                    new FileOutputStream(EVENT_TRACE_FILE_PATH), 1 << 16);
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
            EVENT_TRACE_FILE = new BufferedOutputStream(
                    new FileOutputStream(EVENT_TRACE_FILE_PATH), 1 << 16);
            eventCount = 0;
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
        // Lock-free fast path once the cap is reached: loop-heavy code keeps
        // calling this, so avoid acquiring the lock for every dropped event.
        if (eventCount >= EVENTS_MAX) {
            return;
        }
        try {
            synchronized (LOCK) {
                if (eventCount >= EVENTS_MAX) {
                    return;
                }
                eventCount++;
                if (THREAD_SUPPORT) {
                    EVENT_TRACE_FILE.write(
                            JCodec.encodeThreadId((int) Thread.currentThread().getId()));
                }
                EVENT_TRACE_FILE.write(encodedEvent);
            }
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

    /**
     * Records a condition event inline and returns its value, so a loop test
     * such as {@code while (cond)} can be instrumented as
     * {@code while (evalCondition(id, (cond)))} without hoisting the condition
     * into the body (which would break on {@code continue}/{@code break}).
     */
    public static boolean evalCondition(int eventID, boolean condition) {
        write(JCodec.encodeConditionEvent(eventID, condition));
        return condition;
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

    // Catch-all so that getLen(...) type-checks for values without a length
    // (e.g. primitives/plain objects); it is never reached at runtime because
    // the instrumentation guards the call with hasLen(...), which is false here.
    public static int getLen(Object ignored) {
        return 0;
    }

    public static boolean hasLen(Collection<?> object) {
        return object != null;
    }

    public static boolean hasLen(Object[] object) {
        return object != null;
    }

    public static boolean hasLen(byte[] object) {
        return object != null;
    }

    public static boolean hasLen(short[] object) {
        return object != null;
    }

    public static boolean hasLen(int[] object) {
        return object != null;
    }

    public static boolean hasLen(long[] object) {
        return object != null;
    }

    public static boolean hasLen(float[] object) {
        return object != null;
    }

    public static boolean hasLen(double[] object) {
        return object != null;
    }

    public static boolean hasLen(char[] object) {
        return object != null;
    }

    public static boolean hasLen(boolean[] object) {
        return object != null;
    }

    public static boolean hasLen(String object) {
        return object != null;
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
