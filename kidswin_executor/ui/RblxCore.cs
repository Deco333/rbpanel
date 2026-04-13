using System;
using System.Runtime.InteropServices;

namespace KidsWinUI
{
    public static class RblxCore
    {
        private const string DllName = "KidsWinAPI.dll";

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern bool Initialize();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern uint FindRobloxProcess();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern bool Connect(uint pid);

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern void Disconnect();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi)]
        public static extern int ExecuteScript([MarshalAs(UnmanagedType.LPStr)] string source, int length);

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern IntPtr GetDataModel();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern uint GetRobloxPid();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern void RedirConsole();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        public static extern int GetJobCount();

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi)]
        public static extern int GetLastExecError([MarshalAs(UnmanagedType.LPStr)] StringBuilder buffer, int bufferSize);

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        [return: MarshalAs(UnmanagedType.I1)]
        public static extern bool ReadMemory(IntPtr address, IntPtr buffer, int size);

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall)]
        [return: MarshalAs(UnmanagedType.I1)]
        public static extern bool WriteMemory(IntPtr address, IntPtr buffer, int size);

        [DllImport(DllName, CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi)]
        [return: MarshalAs(UnmanagedType.I1)]
        public static extern bool GetClientInfo([MarshalAs(UnmanagedType.LPStr)] StringBuilder buffer, int bufferSize);
    }
}
