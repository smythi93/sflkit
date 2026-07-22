package de.cispa.sflkitlib.events.event;

public enum JEventType {
    J_LINE(0),
    J_BRANCH(1),
    J_FUNCTION_ENTER(2),
    J_FUNCTION_EXIT(3),
    J_FUNCTION_ERROR(4),
    J_DEF(5),
    J_USE(6),
    J_CONDITION(7),
    J_LOOP_BEGIN(8),
    J_LOOP_HIT(9),
    J_LOOP_END(10),
    J_LEN(11),
    J_TEST_START(12),
    J_TEST_END(13),
    J_TEST_LINE(14),
    J_TEST_DEF(15),
    J_TEST_USE(16),
    J_TEST_ASSERT(17);

    private final int value;

    JEventType(int value) {
        this.value = value;
    }

    public int getValue() {
        return value;
    }
}