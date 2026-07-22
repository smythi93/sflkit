package de.cispa.sflkitlib.events.event;

public class JDefEvent extends JEvent {
    private final String var;
    private Integer varID = null;
    private Object value = null;
    private String type = null;

    public JDefEvent(String file, int line, int eventID, String var) {
        super(file, line, eventID, JEventType.J_DEF);
        this.var = var;
    }

    public JDefEvent(String file, int line, int eventID, String var, Integer varID) {
        super(file, line, eventID, JEventType.J_DEF);
        this.var = var;
        this.varID = varID;
    }

    public JDefEvent(
            String file, int line, int eventID, String var, Integer varID, Object value,
            String type
    ) {
        super(file, line, eventID, JEventType.J_DEF);
        this.var = var;
        this.varID = varID;
        this.value = value;
        this.type = type;
    }

    public String getVar() {
        return var;
    }

    public Integer getVarID() {
        return varID;
    }

    public Object getValue() {
        return value;
    }

    public String getType() {
        return type;
    }
}
