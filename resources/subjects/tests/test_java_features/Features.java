import java.util.ArrayList;
import java.util.List;

public class Features {
    interface Shape { double area(); }

    enum Color { RED, GREEN, BLUE }

    static class Box<T> {
        private final T value;
        Box(T value) { this.value = value; }
        T get() { return value; }
    }

    static int counter = 0;

    static <T> int size(List<T> xs) {
        int n = 0;
        for (T x : xs) { n = n + 1; }
        return n;
    }

    static int classify(int x) {
        switch (x % 3) {
            case 0: return 100;
            case 1: return 200;
            default: return 300;
        }
    }

    static int sum(int... xs) {
        int s = 0;
        for (int i = 0; i < xs.length; i = i + 1) { s = s + xs[i]; }
        return s;
    }

    static String pick(Object o) {
        String r = (o instanceof String) ? ("str:" + (String) o) : "other";
        try {
            if (o == null) { throw new IllegalStateException("null"); }
            return r;
        } catch (Exception e) {
            return "err";
        } finally {
            counter = counter + 1;
        }
    }

    public static void main(String[] args) {
        List<Integer> xs = new ArrayList<>();
        xs.add(1);
        xs.add(2);
        int total = size(xs) + classify(7) + sum(1, 2, 3);
        Box<String> b = new Box<>("hi");
        Shape sq = () -> 4.0;
        String s = pick(b.get()) + pick(null) + sq.area();
        Color c = Color.GREEN;
        String out = (c == Color.GREEN) ? s : "no";
        int doI = 0;
        do { doI = doI + 1; } while (doI < 2);
    }
}
