package de.cispa.sflkitlib.events;

import java.nio.charset.StandardCharsets;

public class JCodec {
    public static byte getByteLength(int x) {
        if (x >= 0) {
            if (x < 256) {
                return 1;
            } else if (x < 65536) {
                return 2;
            } else if (x < 16777216) {
                return 3;
            } else {
                return 4;
            }
        } else {
            return 4;
        }
    }

    public static byte[] encodeInt2(short x) {
        byte[] result = new byte[2];
        result[0] = (byte) ((x >> 8) & 0xFF);
        result[1] = (byte) (x & 0xFF);
        return result;
    }

    public static byte[] encodeInt(int x) {
        byte[] result = new byte[4];
        for (int i = 3; i >= 0; i--) {
            result[i] = (byte) (x & 0xFF);
            x >>= 8;
        }
        return result;
    }

    private static void write1(int value, byte length, byte[] result, int offset) {
        result[offset] = length;
        for (int i = length; i >= 1; i--) {
            result[offset + i] = (byte) (value & 0xFF);
            value >>= 8;
        }
    }

    public static byte[] encodeEvent(int eventID) {
        byte length = getByteLength(eventID);
        byte[] result = new byte[length + 1];
        write1(eventID, length, result, 0);
        return result;
    }

    public static byte[] encodeBaseDefEvent(int eventID, int varID) {
        byte LengthEvent = getByteLength(eventID);
        byte LengthVar = getByteLength(varID);
        byte[] result = new byte[LengthEvent + LengthVar + 2];
        write1(eventID, LengthEvent, result, 0);
        write1(varID, LengthVar, result, LengthEvent + 1);
        return result;
    }

    public static byte[] encodeDefEvent(int eventID, int varID, byte[] value, String type) {
        byte LengthEvent = getByteLength(eventID);
        byte LengthVar = getByteLength(varID);
        byte[] encodedType = type.getBytes(StandardCharsets.UTF_8);
        byte[] result = new byte[LengthEvent + LengthVar + value.length + encodedType.length + 8];
        write1(eventID, LengthEvent, result, 0);
        write1(varID, LengthVar, result, LengthEvent + 1);
        byte[] length = encodeInt(value.length);
        for (int i = 0; i < 4; i++) {
            result[LengthEvent + LengthVar + i + 2] = length[i];
        }
        for (int i = 0; i < value.length; i++) {
            result[LengthEvent + LengthVar + 6 + i] = value[i];
        }
        byte[] lengthType = encodeInt2((short) encodedType.length);
        for (int i = 0; i < 2; i++) {
            result[LengthEvent + LengthVar + value.length + 6 + i] = lengthType[i];
        }
        for (int i = 0; i < encodedType.length; i++) {
            result[LengthEvent + LengthVar + value.length + 8 + i] = encodedType[i];
        }
        return result;
    }

    public static byte[] encodeFunctionExitEvent(int eventID, byte[] value, String type) {
        byte LengthEvent = getByteLength(eventID);
        byte[] encodedType = type.getBytes(StandardCharsets.UTF_8);
        byte[] result = new byte[LengthEvent + value.length + encodedType.length + 7];
        write1(eventID, LengthEvent, result, 0);
        byte[] length = encodeInt(value.length);
        for (int i = 0; i < 4; i++) {
            result[LengthEvent + i + 1] = length[i];
        }
        for (int i = 0; i < value.length; i++) {
            result[LengthEvent + 5 + i] = value[i];
        }
        byte[] lengthType = encodeInt2((short) encodedType.length);
        for (int i = 0; i < 2; i++) {
            result[LengthEvent + value.length + 5 + i] = lengthType[i];
        }
        for (int i = 0; i < encodedType.length; i++) {
            result[LengthEvent + value.length + 7 + i] = encodedType[i];
        }
        return result;
    }

    public static byte[] encodeConditionEvent(int eventID, boolean value) {
        byte LengthEvent = getByteLength(eventID);
        byte[] result = new byte[LengthEvent + 2];
        write1(eventID, LengthEvent, result, 0);
        result[LengthEvent + 1] = (byte) (value ? 1 : 0);
        return result;
    }

    public static byte[] encodeUseEvent(int eventID, int varID) {
        byte LengthEvent = getByteLength(eventID);
        byte LengthVar = getByteLength(varID);
        byte[] result = new byte[LengthEvent + LengthVar + 2];
        write1(eventID, LengthEvent, result, 0);
        write1(varID, LengthVar, result, LengthEvent + 1);
        return result;
    }

    public static byte[] encodeLenEvent(int eventID, int varID, int length) {
        byte LengthEvent = getByteLength(eventID);
        byte LengthVar = getByteLength(varID);
        byte LengthLength = getByteLength(length);
        byte[] result = new byte[LengthEvent + LengthVar + LengthLength + 3];
        write1(eventID, LengthEvent, result, 0);
        write1(varID, LengthVar, result, LengthEvent + 1);
        write1(length, LengthLength, result, LengthEvent + LengthVar + 2);
        return result;
    }
}
