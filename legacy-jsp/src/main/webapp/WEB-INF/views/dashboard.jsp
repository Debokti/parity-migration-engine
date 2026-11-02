<%@ page contentType="text/html;charset=UTF-8" %><%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>Dashboard</title>
  <link rel="stylesheet" type="text/css" href="${pageContext.request.contextPath}/assets/styles.css">
</head>
<body bgcolor="#CCCCCC" text="#000000" link="#003399" vlink="#003399">
<%@ include file="/WEB-INF/views/header.jspf" %>
<%@ include file="/WEB-INF/views/mfe-popup.jspf" %>
  <table width="100%" border="0" cellpadding="2" cellspacing="0">
    <tr><td class="crumb">Home / Dashboard</td></tr>
  </table>
  <hr size="1" noshade>
  <div class="pageTitle">Supplier Dashboard</div>
  <table width="610" border="0" cellpadding="4" cellspacing="1" bgcolor="#999999">
    <tr><td colspan="3" class="sectionTitle">Supplier Program Summary</td></tr>
    <tr class="rowEven">
      <td colspan="3" id="supplier-summary" data-testid="supplier-summary"><b>${dashboard.supplierId} — ${dashboard.supplierName} — ${dashboard.programStatus}</b></td>
    </tr>
    <tr>
      <td width="33%" class="metricCell" id="facility-limit" data-testid="facility-limit">Facility limit: ${dashboard.facilityLimit}</td>
      <td width="33%" class="metricCell" id="utilized-amount" data-testid="utilized-amount">Utilized: ${dashboard.utilizedAmount}</td>
      <td width="34%" class="metricCell" id="available-limit" data-testid="available-limit">Available: ${dashboard.availableLimit}</td>
    </tr>
  </table>
  <br>
  <table width="610" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999" data-testid="recent-activity">
    <tr><td colspan="3" class="sectionTitle">Recent Activity</td></tr>
    <tr class="tableHeader">
      <th align="left">Reference</th>
      <th align="right">Amount</th>
      <th align="center">Currency</th>
    </tr>
    <c:forEach var="r" items="${dashboard.recentActivity}" varStatus="status">
      <tr class="${status.index % 2 == 0 ? 'rowEven' : 'rowOdd'}" bgcolor="${status.index % 2 == 0 ? '#FFFFFF' : '#F2F4F7'}" data-testid="activity-row">
        <td>${r.ref}</td>
        <td align="right">${r.requestedAmount}</td>
        <td align="center">${r.currency}</td>
      </tr>
    </c:forEach>
  </table>
<%@ include file="/WEB-INF/views/footer.jspf" %>
</body>
</html>