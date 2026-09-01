public class Threads {
    static int work(int n) {
        int s = 0;
        for (int i = 0; i < n; i = i + 1) { s = s + i; }
        return s;
    }

    public static void main(String[] args) throws InterruptedException {
        Runnable r = () -> work(3);
        Thread t1 = new Thread(r);
        Thread t2 = new Thread(r);
        t1.start();
        t2.start();
        t1.join();
        t2.join();
        work(2);
    }
}
