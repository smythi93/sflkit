package de.cispa.sflkitlib.events.event;

public class JLineEvent extends JEvent {
    public JLineEvent(String file, int line, int eventID) {
        super(file, line, eventID, JEventType.J_LINE);
    }
}
