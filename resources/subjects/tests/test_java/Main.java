public class Main {
    static int middle(int x, int y, int z) {
        int m = z;
        if (y < z) {
            if (x < y) {
                m = y;
            } else if (x < z) {
                m = x;
            }
        } else {
            if (x > y) {
                m = y;
            } else if (x > z) {
                m = x;
            }
        }
        return m;
    }

    public static void main(String[] args) {
        int a = middle(3, 3, 5);
        int b = middle(2, 1, 3);
    }
}
