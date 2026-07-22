package de.cispa.sflkitlib.events.event;

public abstract class JEvent {
    private final String file;
    private final int line;
    private final int eventID;
    private final JEventType eventType;

    public JEvent(String file, int line, int eventID, JEventType eventType) {
        this.file = file;
        this.line = line;
        this.eventID = eventID;
        this.eventType = eventType;
    }

    public String getFile() {
        return file;
    }

    public int getLine() {
        return line;
    }

    public int getEventID() {
        return eventID;
    }

    public JEventType getEventType() {
        return eventType;
    }
}
