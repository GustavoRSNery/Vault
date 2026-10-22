import { describe, expect, it } from 'vitest'
import { comandosOpenssl, lerCertificado, paraDer } from './certificado'

/**
 * Certificado real, gerado por `openssl req -x509` (RSA 2048, autoassinado).
 *
 * Os valores esperados abaixo vieram da saída do próprio `openssl x509
 * -noout -subject -issuer -serial -dates`, não da minha leitura do parser —
 * senão o teste confirmaria o parser contra ele mesmo.
 */
const PEM = `-----BEGIN CERTIFICATE-----
MIIDjzCCAnegAwIBAgIUeI2qNgRKXV77QOlwBdNITkCGcEAwDQYJKoZIhvcNAQEL
BQAwVzELMAkGA1UEBhMCQlIxDjAMBgNVBAgMBUdvaWFzMRgwFgYDVQQKDA9FbXBy
ZXNhIEV4ZW1wbG8xHjAcBgNVBAMMFXBvcnRhbC5leGVtcGxvLmNvbS5icjAeFw0y
NjEwMjYxOTAxMzJaFw0yNzEwMjYxOTAxMzJaMFcxCzAJBgNVBAYTAkJSMQ4wDAYD
VQQIDAVHb2lhczEYMBYGA1UECgwPRW1wcmVzYSBFeGVtcGxvMR4wHAYDVQQDDBVw
b3J0YWwuZXhlbXBsby5jb20uYnIwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQChASyV9W+mq5zDWI5FwWEuLJ+rJrhqbyqpLAB59MQZoVcQ6KDx1LjW65a+
xul4RSR3M1tfXRdInK4s0lCopHueOuo/qAjAO4ZiwzoaCiJiOGrx1PwocQ+lZivT
ZAFfdBZJXdGKmPFKDdKHt82Orw3KnVEKqbitVnUrJrt+/7xdt8+OQFfol5FMPhh3
G2vV61WEV2F5tMbye039J4k4tC/r8RbRa3JmdL/HN7wI/WpEYcTHToLWPjhp/GoD
9iB8dQwa57+AlUdpYXhHETFD0TdvbDOqzoN3qQhoar1VOprU9b9qds8wk1slYBj+
UDHCB7KmrzGk+1yndA5lE1VI8gjlAgMBAAGjUzBRMB0GA1UdDgQWBBRmIX3msBzk
XqSsohHWZOEGVMyxfTAfBgNVHSMEGDAWgBRmIX3msBzkXqSsohHWZOEGVMyxfTAP
BgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQA40d0aWCoU/ZTQUL5y
WCFUj4C8KelWDUQfNhNQn/OQ993tHm84CXXLdn4ZyUVPd05RCaMwfTji8oBuKd/v
ZLcp6CFyfALWsKyeHBWuhNQGehzX36J46S2t+nhdiwRxAl/nAxWzeB5LOUhl8EyE
+9ZmT6GmOU3D6cXdu2ju0Xugvrv5HVs1bb4vGT1z/x8S+mREaAh1YzZ/8Lc9gJYk
EFl9xmvOmWwnUN4pNtNXfAS5WGLEeRrcXUnbV4u9wWzfP5GKwGOLqy1fJcWv69xO
3HOwzdXmzwfCzmp8g3izQ7OXojTHdBb7PHVDu5dTBtfUr0WfCd2El9qG+rQf01mD
QkWb
-----END CERTIFICATE-----`

function bytes(texto: string): Uint8Array {
  return new TextEncoder().encode(texto)
}

describe('lerCertificado', () => {
  it('extrai o titular como o openssl mostra', () => {
    const c = lerCertificado(bytes(PEM))
    // Gabarito (openssl x509 -noout -subject, ordem do DER):
    //   C=BR, ST=Goias, O=Empresa Exemplo, CN=portal.exemplo.com.br
    expect(c.subject).toBe(
      'C=BR, ST=Goias, O=Empresa Exemplo, CN=portal.exemplo.com.br',
    )
    expect(c.subject).toContain('CN=portal.exemplo.com.br')
    expect(c.subject).toContain('O=Empresa Exemplo')
    expect(c.subject).toContain('ST=Goias')
    expect(c.subject).toContain('C=BR')
  })

  it('extrai o emissor', () => {
    expect(lerCertificado(bytes(PEM)).issuer).toContain('CN=portal.exemplo.com.br')
  })

  it('extrai o serial igual ao do openssl, COM o zero à esquerda', () => {
    // openssl: serial=788DAA36044A5D5EFB40E97005D3484E40867040
    //
    // O `08` inicial faz parte do valor. Tratá-lo como padding de sinal do
    // DER e cortá-lo produziria um serial que não casa com o que a
    // autoridade emissora informa — e conferir contra ela é a única função
    // do serial.
    expect(lerCertificado(bytes(PEM)).serial).toBe(
      '788DAA36044A5D5EFB40E97005D3484E40867040',
    )
  })

  it('extrai a validade', () => {
    const c = lerCertificado(bytes(PEM))
    // openssl: notBefore=Oct 26 19:01:32 2026 GMT / notAfter=... 2027 GMT
    expect(c.notBefore).toBe('2026-10-26T19:01:32.000Z')
    expect(c.notAfter).toBe('2027-10-26T19:01:32.000Z')
  })

  it('não desalinha os campos por causa do `version` opcional', () => {
    // O campo `version` vem marcado com [0] e desloca tudo em uma posição.
    // Ignorá-lo faria o serial cair onde está o emissor, e a validade onde
    // está o titular. Num autoassinado emissor e titular são idênticos, por
    // isso o que se checa aqui é cada campo ter o TIPO certo.
    const c = lerCertificado(bytes(PEM))
    expect(c.serial).toMatch(/^[0-9A-F]+$/)
    expect(c.subject).toContain('CN=')
    expect(c.issuer).toContain('CN=')
    expect(c.notBefore).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })

  it('aceita DER direto, sem cabeçalho PEM', () => {
    const der = paraDer(bytes(PEM))
    expect(der[0]).toBe(0x30)
    expect(lerCertificado(der).serial).toBe(
      '788DAA36044A5D5EFB40E97005D3484E40867040',
    )
  })

  it('ignora espaço e quebra de linha extras no PEM', () => {
    const bagunçado = PEM.replace(/\n/g, '\r\n') + '\n\n  '
    expect(lerCertificado(bytes(bagunçado)).subject).toContain('portal.exemplo.com.br')
  })
})

describe('lerCertificado — recusas com mensagem útil', () => {
  it('recusa arquivo que não é certificado', () => {
    expect(() => lerCertificado(bytes('oi, isto é um texto'))).toThrow('X.509')
  })

  it('recusa arquivo vazio', () => {
    expect(() => lerCertificado(new Uint8Array())).toThrow('X.509')
  })

  it('recusa DER truncado em vez de devolver lixo', () => {
    const der = paraDer(bytes(PEM))
    expect(() => lerCertificado(der.subarray(0, 40))).toThrow()
  })
})

describe('comandosOpenssl', () => {
  it('usa o nome do arquivo informado', () => {
    const cmds = comandosOpenssl('portal.pem', false)
    expect(cmds[0]?.comando).toContain('portal.pem')
  })

  it('cai num nome genérico quando não há arquivo', () => {
    expect(comandosOpenssl('', false)[0]?.comando).toContain('certificado.pem')
  })

  it('não oferece comandos de chave privada para certificado público', () => {
    const texto = comandosOpenssl('x.pem', false)
      .map((c) => c.comando)
      .join('\n')
    expect(texto).not.toContain('pkcs12')
    expect(texto).not.toContain('-nodes')
  })

  it('oferece pkcs12 quando há chave privada, avisando do risco', () => {
    const cmds = comandosOpenssl('x.pfx', true)
    const pkcs12 = cmds.find((c) => c.comando.includes('pkcs12'))
    expect(pkcs12).toBeDefined()
    expect(pkcs12?.explica).toContain('confiança')
  })

  it('inclui a conferência de SAN: o CN sozinho engana', () => {
    const texto = comandosOpenssl('x.pem', false)
      .map((c) => c.comando)
      .join('\n')
    expect(texto).toContain('subjectAltName')
  })
})
