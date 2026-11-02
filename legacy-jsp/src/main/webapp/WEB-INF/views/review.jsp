<%@ page contentType="text/html;charset=UTF-8" import="java.util.List" %><%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>Review</title>
  <link rel="stylesheet" type="text/css" href="${pageContext.request.contextPath}/assets/styles.css">
</head>
<body bgcolor="#CCCCCC" text="#000000" link="#003399" vlink="#003399">
<%@ include file="/WEB-INF/views/header.jspf" %>
  <table width="100%" border="0" cellpadding="2" cellspacing="0">
    <tr><td class="crumb">Home / Invoices / Drawdown / Attachments / Review</td></tr>
  </table>
  <hr size="1" noshade>
  <div class="pageTitle">Review &amp; Submit</div>
  <c:if test="${not empty errors}">
    <div id="validation-errors" data-testid="validation-errors" class="error">
      <c:forEach var="e" items="${errors}">${e.key}: ${e.value}<br></c:forEach>
    </div>
    <br>
  </c:if>
<%
  Object draftObj = session.getAttribute("SCF_DRAFT_REQUEST");
  Object invRefs = "";
  Object reqAmt = "";
  Object curr = "";
  Object tenor = "";
  Object ben = "";
  List<?> attachments = null;
  if (draftObj != null) {
    try {
      Class<?> cls = draftObj.getClass();
      invRefs = cls.getField("invoiceRefs").get(draftObj);
      reqAmt = cls.getField("requestedAmount").get(draftObj);
      curr = cls.getField("currency").get(draftObj);
      tenor = cls.getField("tenorDays").get(draftObj);
      ben = cls.getField("beneficiaryCode").get(draftObj);
      if (ben == null || ben.toString().isBlank()) {
        ben = "BEN-US-001";
        cls.getField("beneficiaryCode").set(draftObj, ben);
      }
      attachments = (List<?>) cls.getField("attachments").get(draftObj);
    } catch (Exception ignored) {}
  }
%>
  <table width="520" border="0" cellpadding="4" cellspacing="1" bgcolor="#999999" data-testid="review-summary-table">
    <tr><td colspan="2" class="sectionTitle">Drawdown Request Summary (<a href="${pageContext.request.contextPath}/drawdown">Edit Parameters</a>)</td></tr>
    <tr><td width="160" class="formLabel">Selected Invoices:</td><td class="formField"><%= invRefs != null ? invRefs : "" %></td></tr>
    <tr><td class="formLabel">Requested Amount:</td><td class="formField"><%= reqAmt != null ? reqAmt : "" %></td></tr>
    <tr><td class="formLabel">Currency:</td><td class="formField"><%= curr != null ? curr : "" %></td></tr>
    <tr><td class="formLabel">Tenor (Days):</td><td class="formField"><%= tenor != null ? tenor : "" %></td></tr>
    <tr><td class="formLabel">Beneficiary Code:</td><td class="formField"><b><%= ben != null ? ben : "BEN-US-001" %></b></td></tr>
    <tr><td class="formLabel">Submission Token:</td><td class="formField">${sessionScope.submissionToken}</td></tr>
  </table>
  <br>
  <table width="520" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999" data-testid="review-attachments-table">
    <tr><td colspan="4" class="sectionTitle">Supporting Attachments (<a href="${pageContext.request.contextPath}/attachments">Add / Modify</a>)</td></tr>
    <tr class="tableHeader">
      <th align="left">Category</th>
      <th align="left">Filename</th>
      <th align="left">File Type</th>
      <th align="right">Size</th>
    </tr>
    <%
      if (attachments != null && !attachments.isEmpty()) {
        int idx = 0;
        for (Object a : attachments) {
          Object cat = a.getClass().getMethod("category").invoke(a);
          Object fn = a.getClass().getMethod("filename").invoke(a);
          Object ft = a.getClass().getMethod("fileType").invoke(a);
          Object sz = a.getClass().getMethod("sizeBytes").invoke(a);
          String rowClass = (idx % 2 == 0) ? "rowEven" : "rowOdd";
          String rowBg = (idx % 2 == 0) ? "#FFFFFF" : "#F2F4F7";
          idx++;
    %>
      <tr class="<%= rowClass %>" bgcolor="<%= rowBg %>" data-testid="review-attachment-row">
        <td><%= cat %></td>
        <td><%= fn %></td>
        <td><%= ft %></td>
        <td align="right"><%= sz %></td>
      </tr>
    <%
        }
      } else {
    %>
      <tr class="rowEven"><td colspan="4">No attachments added.</td></tr>
    <% } %>
  </table>
  <br>
  <form method="post" action="${pageContext.request.contextPath}/review/submit">
    <input type="hidden" name="submissionToken" value="${sessionScope.submissionToken}">
    <table width="520" border="0" cellpadding="4" cellspacing="1" bgcolor="#999999">
      <tr><td class="sectionTitle">Terms &amp; Authorization</td></tr>
      <tr class="rowEven">
        <td><label><input id="termsAcknowledged" type="checkbox" name="termsAcknowledged"> I acknowledge the terms</label></td>
      </tr>
      <tr bgcolor="#EFEFEF">
        <td><button id="submit-request" data-testid="submit-request" type="submit">Submit request</button></td>
      </tr>
    </table>
  </form>
<%@ include file="/WEB-INF/views/footer.jspf" %>
</body>
</html>
