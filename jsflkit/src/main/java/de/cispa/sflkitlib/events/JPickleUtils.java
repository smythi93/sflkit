package de.cispa.sflkitlib.events;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;

public class JPickleUtils {

    public static byte[] encodeBinInt2 (short x) {
        ByteBuffer buffer = ByteBuffer.allocate(2);
        buffer.order(ByteOrder.LITTLE_ENDIAN);
        buffer.putShort(x);
        return buffer.array();
    }

    public static byte[] encodeBinInt (int x) {
        ByteBuffer buffer = ByteBuffer.allocate(4);
        buffer.order(ByteOrder.LITTLE_ENDIAN);
        buffer.putInt(x);
        return buffer.array();
    }

    public static byte[] encodeLong(long x) {
        if (x == 0) {
            return new byte[0];
        }

        int nbytes = (Long.SIZE - Long.numberOfLeadingZeros(Math.abs(x))) / 8 + 1;
        ByteBuffer buffer = ByteBuffer.allocate(Long.BYTES);
        buffer.order(ByteOrder.LITTLE_ENDIAN);
        for (int i = 0; i < nbytes; i++) {
            buffer.put((byte) (x & 0xFF));
            x >>= 8;
        }
        byte[] result = new byte[nbytes];
        buffer.position(0);
        buffer.get(result);

        // Trim leading 0xff byte if necessary
        if (x < 0 && nbytes > 1) {
            if (result[result.length - 1] == (byte) 0xff && (result[result.length - 2] & 0x80) != 0) {
                byte[] trimmedResult = new byte[result.length - 1];
                System.arraycopy(result, 0, trimmedResult, 0, trimmedResult.length);
                return trimmedResult;
            }
        }

        return result;
    }

    public static byte[] encodeLong8(long value) {
        ByteBuffer buffer = ByteBuffer.allocate(Long.BYTES);
        buffer.order(ByteOrder.LITTLE_ENDIAN);
        buffer.putLong(value);
        return buffer.array();
    }
}