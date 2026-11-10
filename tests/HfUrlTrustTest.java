import org.omega.actions.core.HfUrl;

/** Dependency-free regression checks; run with javac and java from the repository root. */
public final class HfUrlTrustTest {
    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        check(HfUrl.trusted("https://huggingface.co/model"), "Canonical host");
        check(HfUrl.trusted("https://HUGGINGFACE.CO/model"), "Case-insensitive DNS host");
        check(HfUrl.trusted("https://cas-bridge.xethub.hf.co/file?token=abc"), "Signed CDN query");
        check(!HfUrl.trusted("https://huggingface.co/model#fragment"), "Reject fragments");
        check(!HfUrl.trusted("https://huggingface.co.evil.example/file"), "Reject suffix spoof");
        check(!HfUrl.trusted("https://huggingface.co@evil.example/file"), "Reject userinfo spoof");
        check(!HfUrl.trusted("http://huggingface.co/file"), "Require TLS");
        check(!HfUrl.trusted("https://huggingface.co:8443/file"), "Reject alternate port");
        check(!HfUrl.trusted("not-a-url"), "Reject malformed URL");
        check(HfUrl.resolve("org/model", "main", "weights/model.gguf")
                .equals("https://huggingface.co/org/model/resolve/main/weights/model.gguf?download=true"),
                "Canonical GGUF resolution");
        boolean rejected = false;
        try { HfUrl.resolve("org/model", "main", "../escape.gguf"); }
        catch (IllegalArgumentException expected) { rejected = true; }
        check(rejected, "Reject path traversal");
        System.out.println("HfUrlTrustTest: PASS");
    }
}
