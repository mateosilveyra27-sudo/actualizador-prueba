using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace Prueba
{
    public partial class Form1 : Form
    {
        private const string VERSION_ACTUAL = "1.1";
        private const string URL_VERSION = "https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/version.txt";
        private const string URL_EXE = "https://raw.githubusercontent.com/mateosilveyra27-sudo/actualizador-prueba/main/MiPrograma.exe";

        private Button btnPresionar;
        private Label lblMensaje;
        private Button btnActualizar;

        public Form1()
        {
            InitializeComponent();
            ConfigurarInterfaz();
        }

        private void ConfigurarInterfaz()
        {
            this.Text = "Mi programa";
            this.Size = new System.Drawing.Size(500, 300);
            this.StartPosition = FormStartPosition.CenterScreen;

            btnPresionar = new Button
            {
                Text = "Presionar",
                Font = new System.Drawing.Font("Arial", 14),
                Size = new System.Drawing.Size(140, 40),
                Location = new System.Drawing.Point(180, 80)
            };
            btnPresionar.Click += (s, e) => lblMensaje.Text = "Hola";

            lblMensaje = new Label
            {
                Text = "",
                Font = new System.Drawing.Font("Arial", 20),
                Size = new System.Drawing.Size(300, 40),
                Location = new System.Drawing.Point(100, 140),
                TextAlign = System.Drawing.ContentAlignment.MiddleCenter
            };

            btnActualizar = new Button
            {
                Text = "Buscar actualizaciones",
                Size = new System.Drawing.Size(180, 30),
                Location = new System.Drawing.Point(160, 210)
            };
            btnActualizar.Click += async (s, e) => await ComprobarActualizacionAsync();

            this.Controls.Add(btnPresionar);
            this.Controls.Add(lblMensaje);
            this.Controls.Add(btnActualizar);
        }

        private async Task ComprobarActualizacionAsync()
        {
            try
            {
                using (HttpClient client = new HttpClient())
                {
                    client.DefaultRequestHeaders.Add("User-Agent", "Mozilla/5.0");
                    client.DefaultRequestHeaders.Add("Cache-Control", "no-cache");

                    string urlVerNoCache = $"{URL_VERSION}?nocache={DateTimeOffset.UtcNow.ToUnixTimeSeconds()}";
                    string ultimaVersionStr = (await client.GetStringAsync(urlVerNoCache)).Trim();

                    Version vActual = new Version(VERSION_ACTUAL);
                    Version vNueva = new Version(ultimaVersionStr);

                    if (vNueva > vActual)
                    {
                        DialogResult result = MessageBox.Show(
                            $"Hay una nueva versión disponible: {ultimaVersionStr}\nTu versión actual es: {VERSION_ACTUAL}\n\n¿Deseas descargar e instalar la actualización ahora?",
                            "Actualización disponible",
                            MessageBoxButtons.YesNo,
                            MessageBoxIcon.Information
                        );

                        if (result == DialogResult.Yes)
                        {
                            await DescargarYReemplazarAsync();
                        }
                    }
                    else
                    {
                        MessageBox.Show("Ya tenés la última versión.", "Programa actualizado", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo comprobar la actualización.\n\n{ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task DescargarYReemplazarAsync()
        {
            try
            {
                string rutaExeActual = Process.GetCurrentProcess().MainModule.FileName;
                string rutaNuevoExe = rutaExeActual + ".new";
                string rutaScriptBat = Path.Combine(Path.GetTempPath(), "update.bat");

                using (HttpClient client = new HttpClient())
                {
                    string urlExeNoCache = $"{URL_EXE}?nocache={DateTimeOffset.UtcNow.ToUnixTimeSeconds()}";
                    byte[] exeBytes = await client.GetByteArrayAsync(urlExeNoCache);
                    await File.WriteAllBytesAsync(rutaNuevoExe, exeBytes);
                }

                string batContent = $@"
@echo off
timeout /t 2 /nobreak > nul
move /y ""{rutaNuevoExe}"" ""{rutaExeActual}""
start "" ""{rutaExeActual}""
del ""%~f0""
";
                await File.WriteAllTextAsync(rutaScriptBat, batContent);

                MessageBox.Show("El programa se actualizó correctamente. Se reiniciará ahora.", "Actualizado");

                Process.Start(new ProcessStartInfo
                {
                    FileName = rutaScriptBat,
                    CreateNoWindow = true,
                    UseShellExecute = false
                });

                Application.Exit();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error al actualizar: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
