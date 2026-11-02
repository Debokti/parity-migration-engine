<%@ page contentType="text/html;charset=UTF-8" %><%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>Requests</title>
  <link rel="stylesheet" type="text/css" href="${pageContext.request.contextPath}/assets/styles.css">
</head>
<body bgcolor="#CCCCCC" text="#000000" link="#003399" vlink="#003399">
<%@ include file="/WEB-INF/views/header.jspf" %>
  <table width="100%" border="0" cellpadding="2" cellspacing="0">
    <tr><td class="crumb">Home / Requests</td></tr>
  </table>
  <hr size="1" noshade>
  <c:if test="${not empty confirmation}">
    <div id="confirmation" data-testid="confirmation" class="confirmBox">Request ${confirmation} submitted</div>
    <br>
  </c:if>
  <div class="pageTitle">Request History</div>
  <table width="610" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999" data-testid="request-table">
    <tr><td colspan="7" class="sectionTitle">Submitted Drawdown Requests</td></tr>
    <tr class="tableHeader">
      <th align="left">Reference</th>
      <th align="right">Amount</th>
      <th align="center">Currency</th>
      <th align="center">Tenor</th>
      <th align="right">Discount Fee</th>
      <th align="right">Net Payout</th>
      <th align="left">Beneficiary</th>
    </tr>
    <c:forEach var="r" items="${requests}" varStatus="status">
      <tr class="${status.index % 2 == 0 ? 'rowEven' : 'rowOdd'}" bgcolor="${status.index % 2 == 0 ? '#FFFFFF' : '#F2F4F7'}" data-testid="request-row">
        <td>${r.ref}</td>
        <td align="right">${r.requestedAmount}</td>
        <td align="center">${r.currency}</td>
        <td align="center">${r.tenorDays}</td>
        <td align="right">${r.discountFee}</td>
        <td align="right">${r.netPayout}</td>
        <td>${r.beneficiaryCode}</td>
      </tr>
    </c:forEach>
  </table>
<%@ include file="/WEB-INF/views/footer.jspf" %>
</body>
</html>
