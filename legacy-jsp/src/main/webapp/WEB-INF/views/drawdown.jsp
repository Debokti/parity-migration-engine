<%@ page contentType="text/html;charset=UTF-8" %><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>Drawdown</title>
  <link rel="stylesheet" type="text/css" href="${pageContext.request.contextPath}/assets/styles.css">
</head>
<body bgcolor="#CCCCCC" text="#000000" link="#003399" vlink="#003399">
<%@ include file="/WEB-INF/views/header.jspf" %>
<%
  Object draftObj = session.getAttribute("SCF_DRAFT_REQUEST");
  String reqAmt = "";
  String curr = "USD";
  String tenor = "30";
  String ben = "BEN-US-001";
  if (draftObj != null) {
    try {
      Class<?> cls = draftObj.getClass();
      Object a = cls.getField("requestedAmount").get(draftObj);
      Object c = cls.getField("currency").get(draftObj);
      Object t = cls.getField("tenorDays").get(draftObj);
      Object b = cls.getField("beneficiaryCode").get(draftObj);
      if (a != null) reqAmt = a.toString();
      if (c != null && !c.toString().isBlank()) curr = c.toString();
      if (t != null) tenor = t.toString();
      if (b != null && !b.toString().isBlank()) ben = b.toString();
    } catch (Exception ignored) {}
  }
%>
  <table width="100%" border="0" cellpadding="2" cellspacing="0">
    <tr><td class="crumb">Home / Invoices / Drawdown</td></tr>
  </table>
  <hr size="1" noshade>
  <div class="pageTitle">Drawdown Request</div>
  <form method="post" action="${pageContext.request.contextPath}/review">
    <table width="520" border="0" cellpadding="4" cellspacing="1" bgcolor="#999999">
      <tr><td colspan="2" class="sectionTitle">Enter Drawdown Parameters</td></tr>
      <tr>
        <td width="160" class="formLabel">Requested amount:</td>
        <td class="formField">
          <input id="requestedAmount" name="requestedAmount" type="text" size="20" value="<%= reqAmt %>" data-testid="requested-amount">
          <br><font size="1" color="#555555">Min: 1,000.00 | Max: 85% of selected invoices</font>
        </td>
      </tr>
      <tr>
        <td class="formLabel">Currency:</td>
        <td class="formField">
          <select id="currency" name="currency">
            <option value="USD" <%= "USD".equals(curr) ? "selected" : "" %>>USD</option>
            <option value="EUR" <%= "EUR".equals(curr) ? "selected" : "" %>>EUR</option>
          </select>
        </td>
      </tr>
      <tr>
        <td class="formLabel">Tenor:</td>
        <td class="formField">
          <select id="tenorDays" name="tenorDays">
            <option value="30" <%= "30".equals(tenor) ? "selected" : "" %>>30</option>
            <option value="60" <%= "60".equals(tenor) ? "selected" : "" %>>60</option>
            <option value="90" <%= "90".equals(tenor) ? "selected" : "" %>>90</option>
          </select>
        </td>
      </tr>
      <tr>
        <td class="formLabel">Beneficiary:</td>
        <td class="formField">
          <input id="beneficiaryCode" name="beneficiaryCode" type="text" size="20" value="<%= ben %>" data-testid="beneficiary-code">
          <select onchange="if(this.value) document.getElementById('beneficiaryCode').value=this.value;">
            <option value="">-- Registered Accounts --</option>
            <option value="BEN-US-001" <%= "BEN-US-001".equals(ben) ? "selected" : "" %>>BEN-US-001 (Apex US Treasury - USD)</option>
            <option value="BEN-US-123" <%= "BEN-US-123".equals(ben) ? "selected" : "" %>>BEN-US-123 (Citibank NA Clearing - USD)</option>
            <option value="BEN-EU-101" <%= "BEN-EU-101".equals(ben) ? "selected" : "" %>>BEN-EU-101 (Deutsche Bank SEPA - EUR)</option>
          </select>
          <br><font size="1" color="#555555">Format: <b>BEN-XX-000</b> (e.g. <code>BEN-US-001</code>, <code>BEN-US-123</code>, <code>BEN-EU-101</code>)</font>
        </td>
      </tr>
      <tr bgcolor="#EFEFEF">
        <td>&nbsp;</td>
        <td><button id="continue" data-testid="continue" type="submit">Continue</button></td>
      </tr>
    </table>
  </form>
<%@ include file="/WEB-INF/views/footer.jspf" %>
</body>
</html>
