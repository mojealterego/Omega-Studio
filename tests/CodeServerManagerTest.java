import org.omega.actions.CodeServerManager;
import java.io.File;
import java.nio.file.Files;

/** Host-only process-supervisor integration test; NOT an Android binary test. */
public final class CodeServerManagerTest {
    public static void main(String[] args) throws Exception {
        File root=Files.createTempDirectory("omega-codeserver-host-").toFile();
        File bin=new File(root,"usr/bin");if(!bin.mkdirs())throw new AssertionError();
        File node=new File(bin,"node");Files.writeString(node.toPath(),"#!/bin/sh\nexit 0\n");node.setExecutable(true);
        File code=new File(bin,"code-server");
        Files.writeString(code.toPath(),"#!/usr/bin/python3\n"+
            "import http.server,sys\n"+
            "port=int(sys.argv[sys.argv.index('--bind-addr')+1].split(':')[-1])\n"+
            "class H(http.server.BaseHTTPRequestHandler):\n"+
            " def do_GET(self):\n"+
            "  self.send_response(200 if self.path=='/healthz' else 404);self.end_headers()\n"+
            " def log_message(self,*args):pass\n"+
            "http.server.HTTPServer(('127.0.0.1',port),H).serve_forever()\n");
        code.setExecutable(true);
        CodeServerManager manager=CodeServerManager.get();
        try {
            CodeServerManager.Session s=manager.start(root);
            if(!s.url.startsWith("http://127.0.0.1:")||s.password.length()<40)throw new AssertionError("Unprotected server");
            if(!manager.isRunning())throw new AssertionError("Not running");
            if(!manager.start(root).url.equals(s.url))throw new AssertionError("Start is not idempotent");
            manager.stop();
            if(manager.isRunning()||manager.activeUrl()!=null)throw new AssertionError("Server still running");
            System.out.println("CODE_SERVER_SUPERVISOR_PASS");
        }finally {manager.stop();}
    }
}
