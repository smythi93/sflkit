public class NullLen {
    static int probe(String[] arr, String s) {
        int n = -1;
        if (arr != null) {
            n = arr.length;
        }
        return n;
    }

    public static void main(String[] args) {
        int r = probe(null, null);
    }
}
