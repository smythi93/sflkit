public class Loops {
    static int sum(int n) {
        int s = 0;
        int i = 0;
        while (i < n) {
            s = s + i;
            i = i + 1;
        }
        return s;
    }

    public static void main(String[] args) {
        int r = sum(4);
    }
}
