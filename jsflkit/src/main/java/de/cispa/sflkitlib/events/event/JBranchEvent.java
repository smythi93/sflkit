package de.cispa.sflkitlib.events.event;

public class JBranchEvent extends JEvent{
    private final int thenID;
    private final int elseID;

    public JBranchEvent(String file, int line, int eventID, int thenID, int elseID) {
        super(file, line, eventID, JEventType.J_BRANCH);
        this.thenID = thenID;
        this.elseID = elseID;
    }

    public int getThenID() {
        return thenID;
    }

    public int getElseID() {
        return elseID;
    }
}
