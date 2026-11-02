<%@ page contentType="text/html;charset=UTF-8" import="java.util.List,java.util.Map,java.lang.reflect.Field,com.scf.config.AppContext,com.scf.domain.AuthBridgeService" %><!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <title>Attachments</title>
  <link rel="stylesheet" type="text/css" href="${pageContext.request.contextPath}/assets/styles.css">
</head>
<body bgcolor="#CCCCCC" text="#000000" link="#003399" vlink="#003399">
<%@ include file="/WEB-INF/views/header.jspf" %>
  <table width="100%" border="0" cellpadding="2" cellspacing="0">
    <tr><td class="crumb">Home / Invoices / Drawdown / Attachments</td></tr>
  </table>
  <hr size="1" noshade>
  <div class="pageTitle">Supporting Attachments &amp; Staging Area</div>
<%
  String lockErr = (String) session.getAttribute("SCF_UPLOAD_LOCK_ERROR");
  String lockedBy = (String) session.getAttribute("SCF_UPLOAD_CONFIRMED_BY");
  String currentActor = AuthBridgeService.resolveActor(request).actorId();
  boolean ackOrNackDone = false;
  try {
    for (Map<String, Object> r : AppContext.SERVICE.requestList()) {
      if (currentActor.equals(r.get("createdBy")) && ("APPROVED".equals(r.get("approvalStage")) || "REJECTED".equals(r.get("approvalStage")))) {
        ackOrNackDone = true;
        break;
      }
    }
  } catch (Exception ignored) {}
  boolean isLockedForCurrentUser = (lockedBy != null && lockedBy.equals(currentActor) && !ackOrNackDone);
  if (lockErr != null && !lockErr.isBlank()) {
%>
  <div id="upload-lock-error" data-testid="upload-lock-error" class="error"><%= lockErr %></div>
  <br>
<% } %>

  <form id="attachment-form" method="post" action="${pageContext.request.contextPath}/attachments">
    <table width="580" border="0" cellpadding="4" cellspacing="1" bgcolor="#999999">
      <tr><td colspan="2" class="sectionTitle">Upload / Stage Supporting Documents</td></tr>
      <tr>
        <td width="160" class="formLabel">Category:</td>
        <td class="formField">
          <select id="category" name="category" data-testid="attachment-category">
            <option value="INVOICE_COPY">INVOICE_COPY</option>
            <option value="PURCHASE_ORDER">PURCHASE_ORDER</option>
            <option value="DELIVERY_NOTE">DELIVERY_NOTE</option>
            <option value="OTHER">OTHER</option>
          </select>
        </td>
      </tr>
      <tr>
        <td class="formLabel">Select File(s):</td>
        <td class="formField">
          <input id="documentFile" type="file" multiple="multiple" size="28" data-testid="document-file">
          <div style="font-size:10px; color:#444444;">You can select one or multiple files to add to the Staging Area below.</div>
        </td>
      </tr>
      <tr>
        <td class="formLabel">Filename:</td>
        <td class="formField"><input id="filename" name="filename" type="text" size="28" data-testid="attachment-filename"></td>
      </tr>
      <tr>
        <td class="formLabel">File type:</td>
        <td class="formField"><input id="fileType" name="fileType" type="text" size="28" data-testid="attachment-filetype"></td>
      </tr>
      <tr>
        <td class="formLabel">Size:</td>
        <td class="formField"><input id="sizeBytes" name="sizeBytes" type="text" size="16" data-testid="attachment-size"></td>
      </tr>
      <tr bgcolor="#EFEFEF">
        <td>&nbsp;</td>
        <td>
          <button id="stage-attachment" data-testid="stage-attachment" type="button">Stage File(s)</button>
          &nbsp;
          <button id="add-attachment" data-testid="add-attachment" type="submit">Add attachment</button>
        </td>
      </tr>
    </table>
  </form>

  <br>
  <!-- Staging Area Table -->
  <form id="confirm-upload-form" method="post" action="${pageContext.request.contextPath}/attachments">
    <input type="hidden" name="action" value="confirmUpload">
    <div id="staged-hidden-inputs"></div>
    <table width="610" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999" id="staging-table" data-testid="staging-table">
      <tr><td colspan="6" class="sectionTitle">Staging Area (Select, View, or Delete Before Final Upload)</td></tr>
      <tr class="tableHeader">
        <th width="45" align="center">Upload</th>
        <th align="left">Category</th>
        <th align="left">Filename</th>
        <th align="left">File Type</th>
        <th align="right">Size (bytes)</th>
        <th width="120" align="center">Actions</th>
      </tr>
      <tbody id="staging-tbody">
        <tr id="staging-empty-row" class="rowEven" bgcolor="#FFFFFF">
          <td colspan="6" align="center">No files currently in staging area. Choose files above or click "Stage File(s)".</td>
        </tr>
      </tbody>
      <tr bgcolor="#EFEFEF">
        <td colspan="6" align="right">
          <button id="confirm-upload-btn" data-testid="confirm-upload-btn" type="button">Confirm Final Upload</button>
          &nbsp;
          <a href="${pageContext.request.contextPath}/review">Proceed to Review &raquo;</a>
        </td>
      </tr>
    </table>
  </form>

  <!-- Unselected Staged Files Warning Popup -->
  <div id="unselected-confirm-modal" data-testid="unselected-confirm-modal" style="display:none; margin-top:10px;">
    <table width="520" border="1" cellpadding="6" cellspacing="0" bgcolor="#FFF8DC" bordercolor="#CC6600">
      <tr>
        <td>
          <b>Confirmation Required:</b><br>
          <span id="unselected-confirm-text">Some files are unselected in final upload, these will be lost, continue?</span>
          <div style="margin-top:6px;">
            <button id="confirm-unselected-yes" data-testid="confirm-unselected-yes" type="button">Continue (Discard Unselected)</button>
            &nbsp;
            <button id="confirm-unselected-no" data-testid="confirm-unselected-no" type="button">Cancel</button>
          </div>
        </td>
      </tr>
    </table>
  </div>

  <!-- File Viewer Preview Box -->
  <div id="legacy-file-viewer" data-testid="legacy-file-viewer" style="display:none; margin-top:10px;">
    <table width="580" border="1" cellpadding="6" cellspacing="0" bgcolor="#F2F4F7" bordercolor="#336699">
      <tr>
        <td class="sectionTitle">
          Document Viewer — <span id="viewer-title"></span>
          <button id="viewer-close" data-testid="viewer-close" type="button" style="float:right;">Close</button>
        </td>
      </tr>
      <tr>
        <td>
          <div><b>Category:</b> <span id="viewer-category"></span> | <b>Type:</b> <span id="viewer-type"></span> | <b>Size:</b> <span id="viewer-size"></span> bytes</div>
          <div id="viewer-body" style="margin-top:6px;"></div>
        </td>
      </tr>
    </table>
  </div>

<%
  Object draftObj = session.getAttribute("SCF_DRAFT_REQUEST");
  if (draftObj != null) {
    try {
      Field attField = draftObj.getClass().getField("attachments");
      List<?> attachments = (List<?>) attField.get(draftObj);
      if (attachments != null && !attachments.isEmpty()) {
%>
  <br>
  <table width="610" border="0" cellpadding="3" cellspacing="1" bgcolor="#999999" data-testid="attachments-table">
    <tr>
      <td colspan="5" class="sectionTitle">
        Confirmed Uploaded Documents in Session
        <% if (isLockedForCurrentUser) { %>
          <span id="upload-lock-badge" data-testid="upload-lock-badge" style="color:#FFDDDD; font-weight:normal;">
            [Locked by <%= lockedBy %> — Cannot remove/revert until ACK/NACK &amp; Maker-Checker completes]
          </span>
        <% } %>
      </td>
    </tr>
    <tr class="tableHeader">
      <th align="left">Category</th>
      <th align="left">Filename</th>
      <th align="left">File Type</th>
      <th align="right">Size (bytes)</th>
      <th width="130" align="center">Actions</th>
    </tr>
    <%
      int idx = 0;
      for (Object a : attachments) {
        Object cat = a.getClass().getMethod("category").invoke(a);
        Object fn = a.getClass().getMethod("filename").invoke(a);
        Object ft = a.getClass().getMethod("fileType").invoke(a);
        Object sz = a.getClass().getMethod("sizeBytes").invoke(a);
        String rowClass = (idx % 2 == 0) ? "rowEven" : "rowOdd";
        String rowBg = (idx % 2 == 0) ? "#FFFFFF" : "#F2F4F7";
        int currentIdx = idx;
        idx++;
    %>
      <tr class="<%= rowClass %>" bgcolor="<%= rowBg %>" data-testid="attachment-row">
        <td><%= cat %></td>
        <td><%= fn %></td>
        <td><%= ft %></td>
        <td align="right"><%= sz %></td>
        <td align="center">
          <button type="button" class="view-confirmed-btn" data-cat="<%= cat %>" data-fn="<%= fn %>" data-ft="<%= ft %>" data-sz="<%= sz %>">View</button>
          <form method="post" action="${pageContext.request.contextPath}/attachments" style="display:inline;">
            <input type="hidden" name="action" value="deleteConfirmed">
            <input type="hidden" name="index" value="<%= currentIdx %>">
            <button type="submit" data-testid="delete-confirmed-<%= currentIdx %>" <%= isLockedForCurrentUser ? "title=\"Locked until ACK/NACK Maker-Checker completes\"" : "" %>>Delete</button>
          </form>
        </td>
      </tr>
    <% } %>
    <tr bgcolor="#EFEFEF">
      <td colspan="5" align="right">
        <form method="post" action="${pageContext.request.contextPath}/attachments" style="display:inline;">
          <input type="hidden" name="action" value="revertConfirmed">
          <button id="revert-confirmed-btn" data-testid="revert-confirmed-btn" type="submit">Revert All Uploaded Files</button>
        </form>
      </td>
    </tr>
  </table>
<%
      }
    } catch (Exception ignored) {}
  }
%>
<%@ include file="/WEB-INF/views/footer.jspf" %>
<script type="text/javascript">
(function() {
  var fileInput = document.getElementById('documentFile');
  var categoryInput = document.getElementById('category');
  var filenameInput = document.getElementById('filename');
  var fileTypeInput = document.getElementById('fileType');
  var sizeBytesInput = document.getElementById('sizeBytes');
  var form = document.getElementById('attachment-form');
  var stageBtn = document.getElementById('stage-attachment');
  var stagingTbody = document.getElementById('staging-tbody');
  var confirmBtn = document.getElementById('confirm-upload-btn');
  var confirmForm = document.getElementById('confirm-upload-form');
  var hiddenContainer = document.getElementById('staged-hidden-inputs');
  var modal = document.getElementById('unselected-confirm-modal');
  var modalYes = document.getElementById('confirm-unselected-yes');
  var modalNo = document.getElementById('confirm-unselected-no');
  var viewer = document.getElementById('legacy-file-viewer');
  var viewerClose = document.getElementById('viewer-close');

  var stagedFiles = [];

  function inferMimeType(name) {
    var lower = (name || '').toLowerCase();
    if (lower.endsWith('.pdf')) return 'application/pdf';
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
    if (lower.endsWith('.doc')) return 'application/msword';
    if (lower.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    return 'application/octet-stream';
  }

  function showViewer(item) {
    if (!viewer) return;
    document.getElementById('viewer-title').innerText = item.filename;
    document.getElementById('viewer-category').innerText = item.category;
    document.getElementById('viewer-type').innerText = item.fileType;
    document.getElementById('viewer-size').innerText = String(item.sizeBytes);
    var body = document.getElementById('viewer-body');
    body.innerHTML = '';
    if (item.previewUrl && item.fileType && item.fileType.indexOf('image/') === 0) {
      var img = document.createElement('img');
      img.src = item.previewUrl;
      img.style.maxWidth = '420px';
      img.style.maxHeight = '240px';
      body.appendChild(img);
    } else if (item.previewUrl) {
      var link = document.createElement('a');
      link.href = item.previewUrl;
      link.target = '_blank';
      link.innerText = 'Open "' + item.filename + '" in new browser tab';
      body.appendChild(link);
    } else {
      body.innerText = 'Preview metadata: ' + item.filename + ' (' + item.fileType + ', ' + item.sizeBytes + ' bytes)';
    }
    viewer.style.display = 'block';
  }

  if (viewerClose) {
    viewerClose.onclick = function() {
      viewer.style.display = 'none';
    };
  }

  function renderStaging() {
    if (!stagingTbody) return;
    stagingTbody.innerHTML = '';
    if (stagedFiles.length === 0) {
      var tr = document.createElement('tr');
      tr.className = 'rowEven';
      tr.bgColor = '#FFFFFF';
      tr.innerHTML = '<td colspan="6" align="center">No files currently in staging area. Choose files above or click "Stage File(s)".</td>';
      stagingTbody.appendChild(tr);
      return;
    }
    for (var i = 0; i < stagedFiles.length; i++) {
      (function(idx) {
        var f = stagedFiles[idx];
        var tr = document.createElement('tr');
        tr.className = (idx % 2 === 0) ? 'rowEven' : 'rowOdd';
        tr.bgColor = (idx % 2 === 0) ? '#FFFFFF' : '#F2F4F7';
        tr.setAttribute('data-testid', 'staged-row-' + idx);

        var tdCheck = document.createElement('td');
        tdCheck.align = 'center';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = f.selected;
        cb.setAttribute('data-testid', 'staged-select-' + idx);
        cb.onchange = function() { f.selected = cb.checked; };
        tdCheck.appendChild(cb);

        var tdCat = document.createElement('td');
        tdCat.innerText = f.category;
        var tdFn = document.createElement('td');
        tdFn.innerText = f.filename;
        var tdFt = document.createElement('td');
        tdFt.innerText = f.fileType;
        var tdSz = document.createElement('td');
        tdSz.align = 'right';
        tdSz.innerText = String(f.sizeBytes);

        var tdAct = document.createElement('td');
        tdAct.align = 'center';
        var btnView = document.createElement('button');
        btnView.type = 'button';
        btnView.innerText = 'View';
        btnView.setAttribute('data-testid', 'staged-view-' + idx);
        btnView.onclick = function() { showViewer(f); };

        var btnDel = document.createElement('button');
        btnDel.type = 'button';
        btnDel.innerText = 'Delete';
        btnDel.style.marginLeft = '4px';
        btnDel.setAttribute('data-testid', 'staged-delete-' + idx);
        btnDel.onclick = function() {
          stagedFiles.splice(idx, 1);
          renderStaging();
        };

        tdAct.appendChild(btnView);
        tdAct.appendChild(btnDel);

        tr.appendChild(tdCheck);
        tr.appendChild(tdCat);
        tr.appendChild(tdFn);
        tr.appendChild(tdFt);
        tr.appendChild(tdSz);
        tr.appendChild(tdAct);
        stagingTbody.appendChild(tr);
      })(i);
    }
  }

  function applySelectedFile(file) {
    if (!file) return;
    filenameInput.value = file.name;
    fileTypeInput.value = file.type || inferMimeType(file.name);
    sizeBytesInput.value = String(file.size);
  }

  if (fileInput) {
    fileInput.onchange = function() {
      if (fileInput.files && fileInput.files.length > 0) {
        applySelectedFile(fileInput.files[0]);
        var cat = categoryInput ? categoryInput.value : 'INVOICE_COPY';
        for (var i = 0; i < fileInput.files.length; i++) {
          var f = fileInput.files[i];
          var url = (window.URL && window.URL.createObjectURL) ? window.URL.createObjectURL(f) : null;
          stagedFiles.push({
            category: cat,
            filename: f.name,
            fileType: f.type || inferMimeType(f.name),
            sizeBytes: f.size,
            selected: true,
            previewUrl: url
          });
        }
        renderStaging();
      }
    };
  }

  if (stageBtn) {
    stageBtn.onclick = function() {
      var fn = filenameInput.value;
      if (!fn) return;
      stagedFiles.push({
        category: categoryInput ? categoryInput.value : 'INVOICE_COPY',
        filename: fn,
        fileType: fileTypeInput.value || inferMimeType(fn),
        sizeBytes: parseInt(sizeBytesInput.value || '0', 10) || 0,
        selected: true,
        previewUrl: null
      });
      renderStaging();
    };
  }

  function submitSelectedStaged() {
    hiddenContainer.innerHTML = '';
    var selected = [];
    for (var i = 0; i < stagedFiles.length; i++) {
      if (stagedFiles[i].selected) selected.push(stagedFiles[i]);
    }
    for (var j = 0; j < selected.length; j++) {
      var item = selected[j];
      var fields = [
        ['stagedCategory', item.category],
        ['stagedFilename', item.filename],
        ['stagedFileType', item.fileType],
        ['stagedSizeBytes', String(item.sizeBytes)]
      ];
      for (var k = 0; k < fields.length; k++) {
        var inp = document.createElement('input');
        inp.type = 'hidden';
        inp.name = fields[k][0];
        inp.value = fields[k][1];
        hiddenContainer.appendChild(inp);
      }
    }
    confirmForm.submit();
  }

  if (confirmBtn) {
    confirmBtn.onclick = function() {
      if (stagedFiles.length === 0) return;
      var hasUnselected = false;
      for (var i = 0; i < stagedFiles.length; i++) {
        if (!stagedFiles[i].selected) {
          hasUnselected = true;
          break;
        }
      }
      if (hasUnselected) {
        modal.style.display = 'block';
      } else {
        submitSelectedStaged();
      }
    };
  }

  if (modalYes) {
    modalYes.onclick = function() {
      modal.style.display = 'none';
      submitSelectedStaged();
    };
  }

  if (modalNo) {
    modalNo.onclick = function() {
      modal.style.display = 'none';
    };
  }

  var confirmedViewBtns = document.getElementsByClassName('view-confirmed-btn');
  for (var v = 0; v < confirmedViewBtns.length; v++) {
    (function(btn) {
      btn.onclick = function() {
        showViewer({
          category: btn.getAttribute('data-cat'),
          filename: btn.getAttribute('data-fn'),
          fileType: btn.getAttribute('data-ft'),
          sizeBytes: btn.getAttribute('data-sz'),
          previewUrl: null
        });
      };
    })(confirmedViewBtns[v]);
  }

  if (form) {
    form.onsubmit = function() {
      if (fileInput && fileInput.files && fileInput.files.length > 0) {
        var f = fileInput.files[0];
        if (!filenameInput.value) filenameInput.value = f.name;
        if (!fileTypeInput.value) fileTypeInput.value = f.type || inferMimeType(f.name);
        if (!sizeBytesInput.value) sizeBytesInput.value = String(f.size);
      }
    };
  }
})();
</script>
</body>
</html>
