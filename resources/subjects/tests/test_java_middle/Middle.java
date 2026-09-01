public class Middle {
    static int middle(int x, int y, int z) {
        int m = z;
        if (y < z) {
            if (x < y) {
                m = y;
            } else if (x < z) {
                m = y;
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
        middle(
            Integer.parseInt(args[0]),
            Integer.parseInt(args[1]),
            Integer.parseInt(args[2]));
    }
}
