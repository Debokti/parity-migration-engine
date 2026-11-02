<%@ page contentType="text/html;charset=UTF-8" %><%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core" %><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>Invoices</title>
  <link rel="stylesheet" type="text/css" href="${pageContext.request.contextPath}/assets/styles.css">
</head>
<body bgcolor="#CCCCCC" text="#000000" link="#003399" vlink="#003399">
<%@ include file="/WEB-INF/views/header.jspf" %>
<%@ include file="/WEB-INF/views/mfe-popup.jspf" %>
  <table width="100%" border="0" cellpadding="2" cellspacing="0">
    <tr><td class="crumb">Home / Invoices</td></tr>
  </table>
  <hr size="1" noshade>
  <div class="pageTitle">Invoice Register</div>
  <form method="get" action="${pageContext.request.contextPath}/invoices">
    <table width="610" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999">
      <tr><td colspan="7" class="sectionTitle">Search &amp; Filter Criteria</td></tr>
      <tr class="rowEven">
        <td class="formLabel">Reference:</td>
        <td class="formField"><input id="ref" name="ref" type="text" size="14"></td>
        <td class="formLabel">Status:</td>
        <td class="formField">
          <select id="status" name="status">
            <option value="">All statuses</option>
            <option>APPROVED</option>
            <option>PENDING_APPROVAL</option>
          </select>
        </td>
        <td class="formLabel">Currency:</td>
        <td class="formField">
          <select id="currency" name="currency">
            <option value="">All currencies</option>
            <option>USD</option>
            <option>EUR</option>
          </select>
        </td>
        <td class="formField" align="center">
          <button id="filter-button" data-testid="filter-button" type="submit">Filter</button>
        </td>
      </tr>
    </table>
  </form>
  <form method="post" action="${pageContext.request.contextPath}/invoices/select">
    <table width="610" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999" data-testid="invoice-table">
      <tr class="tableHeader">
        <th width="45" align="center">Select</th>
        <th align="left">Reference</th>
        <th align="left">Status</th>
        <th align="center">Currency</th>
        <th align="right">Amount</th>
        <th align="left">Eligibility</th>
      </tr>
      <c:forEach var="i" items="${invoices}" varStatus="status">
        <tr class="${status.index % 2 == 0 ? 'rowEven' : 'rowOdd'}" bgcolor="${status.index % 2 == 0 ? '#FFFFFF' : '#F2F4F7'}" data-testid="invoice-row">
          <td align="center"><input type="checkbox" name="invoiceRefs" value="${i.ref}" data-testid="invoice-checkbox" ${i.eligibility != 'ELIGIBLE' ? 'disabled' : ''}></td>
          <td>${i.ref}</td>
          <td>${i.status}</td>
          <td align="center">${i.currency}</td>
          <td align="right">${i.amount}</td>
          <td>${i.eligibility}</td>
        </tr>
      </c:forEach>
    </table>
    <br>
    <button id="select-invoices" data-testid="select-invoices" type="submit">Start drawdown</button>
  </form>
<%@ include file="/WEB-INF/views/footer.jspf" %>
</body>
</html>