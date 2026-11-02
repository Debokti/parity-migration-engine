package com.scf.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.scf.domain.AuthBridgeService;
import com.scf.domain.DraftStore;
import com.scf.repository.Database;
import javax.servlet.http.*;
import java.io.IOException;
import java.util.*;

public class ParityDevServlet extends HttpServlet {
    private final ObjectMapper json=new ObjectMapper();
    protected void doGet(HttpServletRequest req,HttpServletResponse res)throws IOException{if(!enabled()){res.sendError(404);return;}Map<String,Object> state=new LinkedHashMap<>();state.put("dashboard",AppContext.SERVICE.dashboard());state.put("invoices",AppContext.SERVICE.invoices(null,null,null));state.put("requests",AppContext.SERVICE.requestList());write(res,state);}
    protected void doPost(HttpServletRequest req,HttpServletResponse res)throws IOException{if(!enabled()){res.sendError(404);return;}Database.reset();AuthBridgeService.bumpEpoch();DraftStore.clearAll();req.getSession().invalidate();write(res,Map.of("reset",true));}
    private boolean enabled(){return !"production".equalsIgnoreCase(System.getenv("PARITY_ENV"))&&Boolean.parseBoolean(System.getProperty("parity.trace","true"));}
    private void write(HttpServletResponse r,Object o)throws IOException{r.setContentType("application/json");json.writeValue(r.getWriter(),o);}
}
