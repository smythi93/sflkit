public class ForLoop {
    static int sum(int n) {
        int s = 0;
        for (int i = 0; i < n; i = i + 1) {
            s = s + i;
        }
        return s;
    }

    public static void main(String[] args) {
        int r = sum(4);
    }
}
