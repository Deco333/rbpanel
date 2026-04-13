using System;
using System.IO;
using System.Text;
using System.Windows;
using Microsoft.Win32;

namespace KidsWinUI
{
    public partial class MainWindow : Window
    {
        private bool _isAttached = false;
        private uint _currentPid = 0;

        public MainWindow()
        {
            InitializeComponent();
            Log("KidsWin Executor initialized.");
            Log("Waiting for Roblox process...");
        }

        private void Log(string message)
        {
            Dispatcher.Invoke(() =>
            {
                string timestamp = DateTime.Now.ToString("HH:mm:ss");
                ConsoleOutput.AppendText($"[{timestamp}] {message}\n");
                ConsoleOutput.ScrollToEnd();
            });
        }

        private void SetStatus(string status, bool connected)
        {
            Dispatcher.Invoke(() =>
            {
                StatusText.Text = $"Status: {status}";
                StatusText.Foreground = connected ? 
                    new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(106, 153, 85)) : 
                    new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(136, 136, 136));
                
                AttachButton.IsEnabled = !connected;
                DetachButton.IsEnabled = connected;
                ExecuteButton.IsEnabled = connected;
                ScriptEditor.IsEnabled = connected;
                
                _isAttached = connected;
            });
        }

        private void AttachButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Log("Initializing KidsWin API...");
                
                if (!RblxCore.Initialize())
                {
                    Log("❌ Failed to initialize KidsWin API. Make sure KidsWinAPI.dll is in the same directory.");
                    MessageBox.Show("Failed to initialize KidsWin API.\n\nPlease ensure KidsWinAPI.dll is in the same directory as this executable.", 
                        "Initialization Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }
                
                Log("Searching for Roblox process...");
                
                uint pid = RblxCore.FindRobloxProcess();
                
                if (pid == 0)
                {
                    Log("❌ No Roblox process found. Please start Roblox first.");
                    MessageBox.Show("No Roblox process found.\n\nPlease start Roblox and join a game first.", 
                        "Process Not Found", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                
                _currentPid = pid;
                ProcessInfo.Text = $"PID: {pid}";
                Log($"Found Roblox process (PID: {pid})");
                
                Log("Connecting to Roblox...");
                
                if (!RblxCore.Connect(pid))
                {
                    Log("❌ Failed to connect to Roblox.");
                    
                    StringBuilder errorBuffer = new StringBuilder(512);
                    RblxCore.GetLastExecError(errorBuffer, 512);
                    Log($"Error: {errorBuffer.ToString()}");
                    
                    MessageBox.Show($"Failed to connect to Roblox.\n\nError: {errorBuffer}", 
                        "Connection Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }
                
                Log("✅ Successfully connected to Roblox!");
                
                // Get client info
                StringBuilder clientInfo = new StringBuilder(512);
                if (RblxCore.GetClientInfo(clientInfo, 512))
                {
                    Log($"Client Info: {clientInfo}");
                }
                
                SetStatus("Connected", true);
                Log("Ready to execute scripts.");
            }
            catch (Exception ex)
            {
                Log($"❌ Exception during attach: {ex.Message}");
                MessageBox.Show($"An error occurred:\n\n{ex.Message}", 
                    "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void DetachButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Log("Disconnecting from Roblox...");
                
                RblxCore.Disconnect();
                
                Log("✅ Disconnected successfully.");
                
                _currentPid = 0;
                ProcessInfo.Text = "PID: --";
                SetStatus("Not connected", false);
            }
            catch (Exception ex)
            {
                Log($"❌ Exception during detach: {ex.Message}");
            }
        }

        private void ExecuteButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string script = ScriptEditor.Text;
                
                if (string.IsNullOrWhiteSpace(script))
                {
                    Log("⚠ Warning: Empty script.");
                    MessageBox.Show("Please enter a script to execute.", 
                        "Empty Script", MessageBoxButton.OK, MessageBoxImage.Warning);
                    return;
                }
                
                Log("Executing script...");
                
                int result = RblxCore.ExecuteScript(script, script.Length);
                
                if (result == 0)
                {
                    Log("✅ Script executed successfully.");
                    ErrorText.Text = "";
                }
                else
                {
                    StringBuilder errorBuffer = new StringBuilder(512);
                    RblxCore.GetLastExecError(errorBuffer, 512);
                    Log($"❌ Execution error: {errorBuffer}");
                    ErrorText.Text = $"Error: {errorBuffer}";
                }
            }
            catch (Exception ex)
            {
                Log($"❌ Exception during execution: {ex.Message}");
                ErrorText.Text = $"Error: {ex.Message}";
            }
        }

        private void LoadScript_Click(object sender, RoutedEventArgs e)
        {
            OpenFileDialog dialog = new OpenFileDialog
            {
                Filter = "Lua Files (*.lua)|*.lua|All Files (*.*)|*.*",
                Title = "Load Lua Script"
            };
            
            if (dialog.ShowDialog() == true)
            {
                try
                {
                    string content = File.ReadAllText(dialog.FileName);
                    ScriptEditor.Text = content;
                    Log($"Loaded script: {Path.GetFileName(dialog.FileName)}");
                }
                catch (Exception ex)
                {
                    Log($"❌ Failed to load script: {ex.Message}");
                    MessageBox.Show($"Failed to load script:\n\n{ex.Message}", 
                        "Load Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        private void SaveScript_Click(object sender, RoutedEventArgs e)
        {
            SaveFileDialog dialog = new SaveFileDialog
            {
                Filter = "Lua Files (*.lua)|*.lua|All Files (*.*)|*.*",
                Title = "Save Lua Script",
                DefaultExt = ".lua"
            };
            
            if (dialog.ShowDialog() == true)
            {
                try
                {
                    File.WriteAllText(dialog.FileName, ScriptEditor.Text);
                    Log($"Saved script: {Path.GetFileName(dialog.FileName)}");
                }
                catch (Exception ex)
                {
                    Log($"❌ Failed to save script: {ex.Message}");
                    MessageBox.Show($"Failed to save script:\n\n{ex.Message}", 
                        "Save Error", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        private void ClearScript_Click(object sender, RoutedEventArgs e)
        {
            ScriptEditor.Clear();
            ErrorText.Text = "";
            Log("Script editor cleared.");
        }

        protected override void OnClosed(EventArgs e)
        {
            if (_isAttached)
            {
                RblxCore.Disconnect();
            }
            base.OnClosed(e);
        }
    }
}
