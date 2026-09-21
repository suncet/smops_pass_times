-- Mail rule action: queue the message, then archive it; the launch agent publishes.
-- Raw mail stays in Application Support and is never committed to GitHub.
using terms from application "Mail"
 on perform mail action with messages theMessages for rule theRule
  tell application "Mail"
   repeat with theMessage in theMessages
    set senderAddress to extract address from sender of theMessage
    if (subject of theMessage contains "SMOPS Pass Times and Shift Schedule") and (senderAddress is in {"gs-ops@lasp.colorado.edu", "elisabeth.vanreijendam@lasp.colorado.edu", "elva7682@laspcolorado.mail.onmicrosoft.com"}) then
     my queueMessage(source of theMessage)
     -- Only archive after the complete raw message has been saved successfully.
     set sourceMailbox to mailbox of theMessage
     set sourceAccount to account of sourceMailbox
     if (name of sourceAccount is "LASP") and (name of sourceMailbox is "Inbox") then
      move theMessage to mailbox "Archive" of sourceAccount
     end if
    end if
   end repeat
  end tell
 end perform mail action with messages
end using terms from

on queueMessage(rawSource)
 set queuePath to (POSIX path of (path to home folder)) & "Library/Application Support/SMOPS Pass Times/queue/"
 do shell script "/bin/mkdir -p " & quoted form of queuePath & " && /bin/chmod 700 " & quoted form of queuePath
 set messageName to do shell script "/usr/bin/uuidgen"
 set temporaryPath to queuePath & messageName & ".tmp"
 set fileHandle to open for access (POSIX file temporaryPath) with write permission
 try
  set eof fileHandle to 0
  write rawSource to fileHandle as «class utf8»
  close access fileHandle
 on error errorText number errorNumber
  try
   close access fileHandle
  end try
  error errorText number errorNumber
 end try
 do shell script "/bin/chmod 600 " & quoted form of temporaryPath & " && /bin/mv " & quoted form of temporaryPath & " " & quoted form of (queuePath & messageName & ".eml")
end queueMessage
