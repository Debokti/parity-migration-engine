package com.scf.config;

import com.scf.repository.Database;
import org.apache.catalina.startup.Tomcat;
import org.apache.catalina.Context;
import org.apache.catalina.loader.WebappLoader;
import java.io.File;
import com.scf.controller.api.ApiServlet;
import com.scf.controller.web.PageServlet;

public class ServerMain {
    public static void main(String[] args) throws Exception {
        Database.initialize(); int port=Integer.getInteger("server.port",8080);
        Tomcat tomcat=new Tomcat();tomcat.setPort(port);tomcat.getConnector();
        File webapp=new File("src/main/webapp").getAbsoluteFile();Context context=tomcat.addWebapp("",webapp.getPath());
        WebappLoader loader=new WebappLoader(ServerMain.class.getClassLoader());loader.setDelegate(true);context.setLoader(loader);
        Tomcat.addServlet(context,"api",new ApiServlet());context.addServletMappingDecoded("/api/v1/*","api");
        Tomcat.addServlet(context,"parity",new ParityDevServlet());context.addServletMappingDecoded("/__parity/*","parity");
        Tomcat.addServlet(context,"page",new PageServlet());for(String mapping:new String[]{"/","/dashboard","/invoices","/invoices/select","/actor/switch","/drawdown","/attachments","/review","/review/submit","/requests"})context.addServletMappingDecoded(mapping,"page");
        context.addFilterDef(new org.apache.tomcat.util.descriptor.web.FilterDef(){{setFilterName("cors");setFilterClass(CorsFilter.class.getName());}});
        org.apache.tomcat.util.descriptor.web.FilterMap filterMap=new org.apache.tomcat.util.descriptor.web.FilterMap();filterMap.setFilterName("cors");filterMap.addURLPatternDecoded("/api/*");context.addFilterMap(filterMap);
        context.addFilterDef(new org.apache.tomcat.util.descriptor.web.FilterDef(){{setFilterName("coexistence");setFilterClass(CoexistenceHeaderFilter.class.getName());}});
        for(String pattern:new String[]{"/api/*","/__parity/*"}){org.apache.tomcat.util.descriptor.web.FilterMap coexistenceMap=new org.apache.tomcat.util.descriptor.web.FilterMap();coexistenceMap.setFilterName("coexistence");coexistenceMap.addURLPatternDecoded(pattern);context.addFilterMap(coexistenceMap);}
        tomcat.start();System.out.println("SCF Server listening on http://localhost:"+port);tomcat.getServer().await();
    }
}
