package de.cispa.sflkitlib.events;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;

public class JPickle {
    private static final byte PROTO = (byte) 0x80;              // 0x80
    private static final byte STOP = '.';                       // .

    private static final byte BINFLOAT = 'G';                   // G
    private static final byte BININT = 'J';                     // J
    private static final byte BININT1 = 'K';                    // K
    private static final byte BININT2 = 'M';                    // M
    private static final byte NONE = 'N';                       // N

    private static final byte SHORT_BINUNICODE = (byte) 0x8c;   // 0x8c
    private static final byte BINUNICODE = 'X';                 // X

    private static final byte BINBYTES = 'B';                   // B
    private static final byte SHORT_BINBYTES = 'C';             // C

    private static final byte NEWTRUE = (byte) 0x88;            // 0x88
    private static final byte NEWFALSE = (byte) 0x89;           // 0x89
    private static final byte LONG1 = (byte) 0x8a;              // 0x8a
    private static final byte LONG4 = (byte) 0x8b;              // 0x8b

    private static final byte MEMOIZE = (byte) 0x94;            // 0x94
    private static final byte FRAME = (byte) 0x95;              // 0x95

    private static final int FRAME_SIZE_MIN = 4;
    private static final int FRAME_SIZE_TARGET = 65536;

    public static byte[] pickle(Object value) {
        try (ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            // Start with protocol marker
            out.write(PROTO);
            out.write(4); // JPickle protocol version 4

            try (ByteArrayOutputStream data = new ByteArrayOutputStream()) {
                boolean frame = true;
                if (value == null) {
                    encode(data);
                } else if (value instanceof Byte) {
                    encode(data, (byte) value);
                } else if (value instanceof Integer) {
                    encode(data, (int) value);
                } else if (value instanceof Short) {
                    encode(data, (short) value);
                } else if (value instanceof Long) {
                    encode(data, (long) value);
                } else if (value instanceof Float || value instanceof Double) {
                    encode(data, ((Number) value).doubleValue());
                } else if (value instanceof Boolean) {
                    encode(data, (Boolean) value);
                } else if (value instanceof String) {
                    encode(data, (String) value);
                    frame = ((String) value).length() < FRAME_SIZE_TARGET;
                } else if (value instanceof byte[]) {
                    encode(data, (byte[]) value);
                    frame = ((byte[]) value).length < FRAME_SIZE_TARGET;
                } else {
                    encode(data);
                }
                // End with STOP opcode
                data.write(STOP);

                if (frame && data.size() >= FRAME_SIZE_MIN) {
                    out.write(FRAME);
                    out.write(JPickleUtils.encodeLong8(data.size()));
                }

                out.write(data.toByteArray());

            }
            return out.toByteArray();
        } catch (IOException e) {
            throw new UnsupportedOperationException(e);
        }
    }

    private static void encode(ByteArrayOutputStream out) {
        out.write(NONE);
    }

    private static void encode(ByteArrayOutputStream out, int value) throws IOException {
        if (value >= 0 && value < 256) {
            out.write(BININT1);
            out.write((byte) value);
        } else if (value >= 0 && value < 65536) {
            out.write(BININT2);
            out.write(JPickleUtils.encodeBinInt2((short) value));
        } else {
            out.write(BININT);
            out.write(JPickleUtils.encodeBinInt(value));
        }
    }


    private static void encode(ByteArrayOutputStream out, long value) throws IOException {
        if (value >= Integer.MIN_VALUE && value <= Integer.MAX_VALUE) {
            encode(out, (int) value); // Use BININT if the long fits in 4 bytes
        } else {
            byte[] longBytes = JPickleUtils.encodeLong(value);
            if (longBytes.length < 256) {
                out.write(LONG1);
                out.write((byte) longBytes.length);
                out.write(longBytes);
            } else {
                out.write(LONG4);
                out.write(JPickleUtils.encodeBinInt(longBytes.length));
                out.write(longBytes);
            }
        }
    }

    private static void encode(ByteArrayOutputStream out, double value) throws IOException {
        out.write(BINFLOAT);
        out.write(ByteBuffer.allocate(8).putDouble(value).array());
    }

    private static void encode(ByteArrayOutputStream out, boolean value) {
        out.write(value ? NEWTRUE : NEWFALSE);
    }

    private static void encode(ByteArrayOutputStream out, String value) throws IOException {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        if (encoded.length < 256) {
            out.write(SHORT_BINUNICODE);
            out.write((byte) encoded.length);
        } else {
            out.write(BINUNICODE);
            out.write(JPickleUtils.encodeBinInt(encoded.length));
        }
        out.write(encoded);
        out.write(MEMOIZE);
    }

    private static void encode(ByteArrayOutputStream out, byte[] value) throws IOException {
        if (value.length < 256) {
            out.write(SHORT_BINBYTES);
            out.write((byte) value.length);
        }  else {
            out.write(BINBYTES);
            out.write(JPickleUtils.encodeBinInt(value.length));
        }
        out.write(value);
        out.write(MEMOIZE);
    }
}
