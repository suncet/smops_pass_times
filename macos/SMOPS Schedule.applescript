-- Mail rule action: store the message locally; the launch agent handles publishing.
-- Raw mail stays in Application Support and is never committed to GitHub.
using terms from application "Mail"
 on perform mail action with messages theMessages for rule theRule
  tell application "Mail"
   repeat with theMessage in theMessages
    if (subject of theMessage contains "SMOPS Pass Times and Shift Schedule") and ((extract address from sender of theMessage) is "gs-ops@lasp.colorado.edu") then
     my queueMessage(source of theMessage)
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
