public class AllEv {
    static int pick(int x, int y) {
        if (x < y) { return x; }
        return y;
    }

    static void noop(int n) {
        int s = 0;
        while (s < n) { s = s + 1; }
    }

    static int risky(int x) {
        if (x < 0) { throw new IllegalArgumentException("neg"); }
        return x;
    }

    static int len(String s) {
        return s.length();
    }

    public static void main(String[] args) {
        int a = pick(2, 5);
        noop(3);
        int b = len("hello");
        try { risky(-1); } catch (Exception e) { }
    }
}
