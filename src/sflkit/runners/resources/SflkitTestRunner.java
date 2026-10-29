import org.junit.runner.Description;
import org.junit.runner.JUnitCore;
import org.junit.runner.Request;
import org.junit.runner.Result;

/**
 * Minimal JUnit launcher used by sflkit's Defects4J runner.
 *
 *   SflkitTestRunner list <pkg.TestClass>    -> prints "pkg.TestClass#method" lines
 *   SflkitTestRunner run  <pkg.TestClass#m>  -> runs one method, exit 0 (pass) / 1 (fail)
 *
 * Each "run" is launched in its own JVM so the instrumentation writes one event
 * trace (EVENTS_PATH) per test case.
 */
public class SflkitTestRunner {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: SflkitTestRunner <list|run> <target>");
            System.exit(2);
        }
        String mode = args[0];
        if (mode.equals("list")) {
            Class<?> cls = Class.forName(args[1]);
            printLeaves(Request.aClass(cls).getRunner().getDescription());
        } else {
            String[] parts = args[1].split("#", 2);
            Class<?> cls = Class.forName(parts[0]);
            Request request =
                    parts.length > 1 ? Request.method(cls, parts[1]) : Request.aClass(cls);
            Result result = new JUnitCore().run(request);
            System.exit(result.wasSuccessful() ? 0 : 1);
        }
    }

    private static void printLeaves(Description description) {
        if (description.getChildren().isEmpty()) {
            if (description.getMethodName() != null) {
                System.out.println(
                        description.getClassName() + "#" + description.getMethodName());
            }
        } else {
            for (Description child : description.getChildren()) {
                printLeaves(child);
            }
        }
    }
}
