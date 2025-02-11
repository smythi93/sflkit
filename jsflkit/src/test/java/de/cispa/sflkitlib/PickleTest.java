package de.cispa.sflkitlib;

import de.cispa.sflkitlib.events.JPickle;
import de.cispa.sflkitlib.events.JPickleUtils;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;

@SuppressWarnings("UnnecessaryUnicodeEscape") public class PickleTest {

    @Test public void encodeLong() {
        assertArrayEquals(new byte[]{}, JPickleUtils.encodeLong(0), "Encoding of 0");
        assertArrayEquals(
                new byte[]{(byte) 0xff, 0x00}, JPickleUtils.encodeLong(255),
                "Encoding of 256"
        );
        assertArrayEquals(
                new byte[]{(byte) 0xff, 0x7f}, JPickleUtils.encodeLong(32767),
                "Encoding of 32767"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x00, (byte) 0xff}, JPickleUtils.encodeLong(-256),
                "Encoding of -256"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x00, (byte) 0x80}, JPickleUtils.encodeLong(-32768),
                "Encoding of -32768"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x80}, JPickleUtils.encodeLong(-128),
                "Encoding of -128"
        );
        assertArrayEquals(new byte[]{0x7f}, JPickleUtils.encodeLong(127), "Encoding of 127");
    }

    @Test public void pickleInt() {
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, 'K', 0x00, '.'}, JPickle.pickle(0),
                "JPickle of 0"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, 'K', 0x01, '.'}, JPickle.pickle(1),
                "JPickle of 1"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'J', (byte) 0xff, (byte) 0xff, (byte) 0xff, (byte) 0xff, '.'
                }, JPickle.pickle(-1), "JPickle of -1"
        );

        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, 'K', (byte) 0xff, '.'}, JPickle.pickle(255),
                "JPickle of 255"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'M', (byte) 0xff, 0x7f, '.'
                }, JPickle.pickle(32767), "JPickle of 32767"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'J', 0x00, (byte) 0xff, (byte) 0xff, (byte) 0xff, '.'
                }, JPickle.pickle(-256), "JPickle of -256"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'J', 0x00, (byte) 0x80, (byte) 0xff, (byte) 0xff, '.'
                }, JPickle.pickle(-32768), "JPickle of -32768"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'J', (byte) 0x80, (byte) 0xff, (byte) 0xff, (byte) 0xff, '.'
                }, JPickle.pickle(-128), "JPickle of -128"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, 'K', 0x7f, '.'}, JPickle.pickle(127),
                "JPickle of 127"
        );
    }

    @Test public void pickleLong() {
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, 'K', 0x00, '.'}, JPickle.pickle(0L),
                "JPickle of 0"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, 'K', 0x01, '.'}, JPickle.pickle(1L),
                "JPickle of 1"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'J', (byte) 0xff, (byte) 0xff, (byte) 0xff, (byte) 0xff, '.'
                }, JPickle.pickle(-1L), "JPickle of -1"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, (byte) 0x8a, 0x05, (byte) 0xb2, (byte) 0xa9, (byte) 0xd1, (byte) 0xc6,
                        'b', '.'
                }, JPickle.pickle(424242424242L), "JPickle of 424242424242"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, (byte) 0x8a, 0x05, 'N', 'V', '.', '9', (byte) 0x9d, '.'
                }, JPickle.pickle(-424242424242L), "JPickle of -424242424242"
        );
    }

    @Test public void pickleBool() {
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, (byte) 0x88, '.'}, JPickle.pickle(true),
                "JPickle of true"
        );
        assertArrayEquals(
                new byte[]{(byte) 0x80, 0x04, (byte) 0x89, '.'}, JPickle.pickle(false),
                "JPickle of false"
        );
    }

    @Test public void pickleFloat() {
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, '\n', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'G', '?', (byte) 0xb9, (byte) 0x99, (byte) 0x99, (byte) 0x99,
                        (byte) 0x99, (byte) 0x99, (byte) 0x9a, '.'
                }, JPickle.pickle(0.1), "JPickle of 0.1"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, '\n', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'G', '?', 0x1a, '6', (byte) 0xe2, (byte) 0xeb, 0x1c, 'C', '-', '.'
                }, JPickle.pickle(0.0001), "JPickle of 0.0001"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, '\n', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'G', '?', (byte) 0xdb, '&', (byte) 0xc9, (byte) 0xb2, 'l', '}', 'L',
                        '.'
                }, JPickle.pickle(0.424242424242D), "JPickle of 0.424242424242"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, '\n', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'G', (byte) 0xbf, (byte) 0xb9, (byte) 0x99, (byte) 0x99, (byte) 0x99,
                        (byte) 0x99, (byte) 0x99, (byte) 0x9a, '.'
                }, JPickle.pickle(-0.1), "JPickle of -0.1"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, '\n', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'G', (byte) 0xbf, 0x1a, '6', (byte) 0xe2, (byte) 0xeb, 0x1c, 'C', '-',
                        '.'
                }, JPickle.pickle(-0.0001), "JPickle of -0.0001"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, '\n', 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'G', (byte) 0xbf, (byte) 0xdb, '&', (byte) 0xc9, (byte) 0xb2, 'l',
                        '}', 'L', '.'
                }, JPickle.pickle(-0.424242424242D), "JPickle of -0.424242424242"
        );
    }

    @Test public void pickleBytes() {
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'C', 0x00, (byte) 0x94, '.'
                }, JPickle.pickle(new byte[]{}), "JPickle of b''"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'C', 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, (byte) 0x94, '.'
                }, JPickle.pickle(new byte[16]), "JPickle of b'0' * 16"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x07, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 'B', 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, (byte) 0x94, '.'
                }, JPickle.pickle(new byte[256]), "JPickle of b'0' * 256"
        );
        byte[] large_expected = new byte[65545];
        large_expected[0] = (byte) 0x80;
        large_expected[1] = 0x04;
        large_expected[2] = 'B';
        large_expected[5] = 0x01;
        large_expected[65543] = (byte) 0x94;
        large_expected[65544] = '.';
        assertArrayEquals(large_expected, JPickle.pickle(new byte[65536]), "JPickle of b'0' * 65536");
    }

    @Test public void pickleStr() {
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, (byte) 0x8c, 0x00, (byte) 0x94, '.'
                }, JPickle.pickle(""), "JPickle of ''"
        );
        assertArrayEquals(
                new byte[]{
                        (byte) 0x80, 0x04, (byte) 0x95, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                        0x00, (byte) 0x8c, 0x01, '0', (byte) 0x94, '.'
                }, JPickle.pickle("0"), "JPickle of '0'"
        );
        byte[] expected = new byte[274];
        expected[0] = (byte) 0x80;
        expected[1] = 0x04;
        expected[2] = (byte) 0x95;
        expected[3] = 0x07;
        expected[4] = 0x01;
        expected[11] = 'X';
        expected[13] = 0x01;
        for (int i = 0; i < 256; i++) {
            expected[i + 16] = '0';
        }
        expected[272] = (byte) 0x94;
        expected[273] = '.';
        assertArrayEquals(
                expected, JPickle.pickle(new String(new char[256]).replace("\0", "0")),
                "JPickle of '0' * 256"
        );
        byte[] large_expected = new byte[65545];
        large_expected[0] = (byte) 0x80;
        large_expected[1] = 0x04;
        large_expected[2] = 'X';
        large_expected[5] = 0x01;
        for (int i = 0; i < 65536; i++) {
            large_expected[i + 7] = '0';
        }
        large_expected[65543] = (byte) 0x94;
        large_expected[65544] = '.';
        assertArrayEquals(
                large_expected, JPickle.pickle(new String(new char[65536]).replace("\0", "0")),
                "JPickle of '0' * 65536"
        );
    }
}
