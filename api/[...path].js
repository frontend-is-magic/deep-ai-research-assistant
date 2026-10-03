// Fail closed until a separately authorized durable API is connected.
module.exports = function handler(_request, response) {
  response.setHeader('Cache-Control', 'no-store');
  response.status(503).json({ error: 'durable_api_not_configured' });
};
