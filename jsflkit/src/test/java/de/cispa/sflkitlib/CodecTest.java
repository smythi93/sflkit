package de.cispa.sflkitlib;

import de.cispa.sflkitlib.events.JCodec;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class CodecTest {

    @Test public void getByteLength() {
        assertEquals(1, JCodec.getByteLength(0));
        assertEquals(1, JCodec.getByteLength(255));
        assertEquals(2, JCodec.getByteLength(256));
        assertEquals(2, JCodec.getByteLength(65535));
        assertEquals(3, JCodec.getByteLength(65536));
        assertEquals(3, JCodec.getByteLength(16777215));
        assertEquals(4, JCodec.getByteLength(16777216));
        assertEquals(4, JCodec.getByteLength(Integer.MAX_VALUE));
        assertEquals(4, JCodec.getByteLength(Integer.MIN_VALUE));
        assertEquals(4, JCodec.getByteLength(-1));
    }

    @Test public void encodeInt2() {
        byte[] result = JCodec.encodeInt2((short) 0x1234);
        assertEquals(0x12, result[0]);
        assertEquals(0x34, result[1]);
    }

    @Test public void encodeInt() {
        byte[] result = JCodec.encodeInt(0x12345678);
        assertEquals(0x12, result[0]);
        assertEquals(0x34, result[1]);
        assertEquals(0x56, result[2]);
        assertEquals(0x78, result[3]);
    }

    @Test public void encodeEvent() {
        byte[] result = JCodec.encodeEvent(0);
        assertEquals(2, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        byte[] result2 = JCodec.encodeEvent(255);
        assertEquals(2, result2.length);
        assertEquals(0x01, result2[0]);
        assertEquals((byte) 0xFF, result2[1]);
        byte[] result3 = JCodec.encodeEvent(256);
        assertEquals(3, result3.length);
        assertEquals(0x02, result3[0]);
        assertEquals(0x01, result3[1]);
        assertEquals(0x00, result3[2]);
        byte[] result4 = JCodec.encodeEvent(65535);
        assertEquals(3, result4.length);
        assertEquals(0x02, result4[0]);
        assertEquals((byte) 0xFF, result4[1]);
        assertEquals((byte) 0xFF, result4[2]);
        byte[] result5 = JCodec.encodeEvent(65536);
        assertEquals(4, result5.length);
        assertEquals(0x03, result5[0]);
        assertEquals(0x01, result5[1]);
        assertEquals(0x00, result5[2]);
        assertEquals(0x00, result5[3]);
    }

    @Test public void encodeBaseDefEvent() {
        byte[] result = JCodec.encodeBaseDefEvent(0, 0);
        assertEquals(4, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        assertEquals(0x01, result[2]);
        assertEquals(0x00, result[3]);
        byte[] result2 = JCodec.encodeBaseDefEvent(255, 255);
        assertEquals(4, result2.length);
        assertEquals(0x01, result2[0]);
        assertEquals((byte) 0xFF, result2[1]);
        assertEquals(0x01, result2[2]);
        assertEquals((byte) 0xFF, result2[3]);
        byte[] result3 = JCodec.encodeBaseDefEvent(256, 256);
        assertEquals(6, result3.length);
        assertEquals(0x02, result3[0]);
        assertEquals(0x01, result3[1]);
        assertEquals(0x00, result3[2]);
        assertEquals(0x02, result3[3]);
        assertEquals(0x01, result3[4]);
        assertEquals(0x00, result3[5]);
        byte[] result4 = JCodec.encodeBaseDefEvent(65535, 65535);
        assertEquals(6, result4.length);
        assertEquals(0x02, result4[0]);
        assertEquals((byte) 0xFF, result4[1]);
        assertEquals((byte) 0xFF, result4[2]);
        assertEquals(0x02, result4[3]);
        assertEquals((byte) 0xFF, result4[4]);
        assertEquals((byte) 0xFF, result4[5]);
        byte[] result5 = JCodec.encodeBaseDefEvent(65536, 65536);
        assertEquals(8, result5.length);
        assertEquals(0x03, result5[0]);
        assertEquals(0x01, result5[1]);
        assertEquals(0x00, result5[2]);
        assertEquals(0x00, result5[3]);
        assertEquals(0x03, result5[4]);
        assertEquals(0x01, result5[5]);
        assertEquals(0x00, result5[6]);
        assertEquals(0x00, result5[7]);
    }

    @Test public void encodeDefEvent() {
        byte[] result = JCodec.encodeDefEvent(0, 0, new byte[0], "Int");
        assertEquals(13, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        assertEquals(0x01, result[2]);
        assertEquals(0x00, result[3]);
        assertEquals(0x00, result[4]);
        assertEquals(0x00, result[5]);
        assertEquals(0x00, result[6]);
        assertEquals(0x00, result[7]);
        assertEquals(0x00, result[8]);
        assertEquals(0x03, result[9]);
        assertEquals('I', result[10]);
        assertEquals('n', result[11]);
        assertEquals('t', result[12]);
        byte[] result2 = JCodec.encodeDefEvent(256, 255, new byte[]{1, 2, 3, 4}, "Int");
        assertEquals(18, result2.length);
        assertEquals(0x02, result2[0]);
        assertEquals(0x01, result2[1]);
        assertEquals(0x00, result2[2]);
        assertEquals(0x01, result2[3]);
        assertEquals((byte) 0xFF, result2[4]);
        assertEquals(0x00, result2[5]);
        assertEquals(0x00, result2[6]);
        assertEquals(0x00, result2[7]);
        assertEquals(0x04, result2[8]);
        assertEquals(1, result2[9]);
        assertEquals(2, result2[10]);
        assertEquals(3, result2[11]);
        assertEquals(4, result2[12]);
        assertEquals(0x00, result2[13]);
        assertEquals(0x03, result2[14]);
        assertEquals('I', result2[15]);
        assertEquals('n', result2[16]);
        assertEquals('t', result2[17]);
    }

    @Test public void encodeFunctionExitEvent() {
        byte[] result = JCodec.encodeFunctionExitEvent(0, new byte[0], "Int");
        assertEquals(11, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        assertEquals(0x00, result[2]);
        assertEquals(0x00, result[3]);
        assertEquals(0x00, result[4]);
        assertEquals(0x00, result[5]);
        assertEquals(0x00, result[6]);
        assertEquals(0x03, result[7]);
        assertEquals('I', result[8]);
        assertEquals('n', result[9]);
        assertEquals('t', result[10]);
        byte[] result2 = JCodec.encodeFunctionExitEvent(256, new byte[]{1, 2, 3, 4}, "Int");
        assertEquals(16, result2.length);
        assertEquals(0x02, result2[0]);
        assertEquals(0x01, result2[1]);
        assertEquals(0x00, result2[2]);
        assertEquals(0x00, result2[3]);
        assertEquals(0x00, result2[4]);
        assertEquals(0x00, result2[5]);
        assertEquals(0x04, result2[6]);
        assertEquals(1, result2[7]);
        assertEquals(2, result2[8]);
        assertEquals(3, result2[9]);
        assertEquals(4, result2[10]);
        assertEquals(0x00, result2[11]);
        assertEquals(0x03, result2[12]);
        assertEquals('I', result2[13]);
        assertEquals('n', result2[14]);
        assertEquals('t', result2[15]);
    }

    @Test public void encodeConditionEvent() {
        byte[] result = JCodec.encodeConditionEvent(0, true);
        assertEquals(3, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        assertEquals(0x01, result[2]);
        byte[] result2 = JCodec.encodeConditionEvent(256, false);
        assertEquals(4, result2.length);
        assertEquals(0x02, result2[0]);
        assertEquals(0x01, result2[1]);
        assertEquals(0x00, result2[2]);
        assertEquals(0x00, result2[3]);
    }

    @Test public void encodeUseEvent() {
        byte[] result = JCodec.encodeUseEvent(0, 0);
        assertEquals(4, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        assertEquals(0x01, result[2]);
        assertEquals(0x00, result[3]);
        byte[] result2 = JCodec.encodeUseEvent(256, 255);
        assertEquals(5, result2.length);
        assertEquals(0x02, result2[0]);
        assertEquals(0x01, result2[1]);
        assertEquals(0x00, result2[2]);
        assertEquals(0x01, result2[3]);
        assertEquals((byte) 0xFF, result2[4]);
    }

    @Test public void encodeLenEvent() {
        byte[] result = JCodec.encodeLenEvent(0, 0, 0);
        assertEquals(6, result.length);
        assertEquals(0x01, result[0]);
        assertEquals(0x00, result[1]);
        assertEquals(0x01, result[2]);
        assertEquals(0x00, result[3]);
        assertEquals(0x01, result[4]);
        assertEquals(0x00, result[5]);
        byte[] result2 = JCodec.encodeLenEvent(256, 255, 65535);
        assertEquals(8, result2.length);
        assertEquals(0x02, result2[0]);
        assertEquals(0x01, result2[1]);
        assertEquals(0x00, result2[2]);
        assertEquals(0x01, result2[3]);
        assertEquals((byte) 0xFF, result2[4]);
        assertEquals(0x02, result2[5]);
        assertEquals((byte) 0xFF, result2[6]);
        assertEquals((byte) 0xFF, result2[7]);
    }
}
